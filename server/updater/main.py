"""
Time Series Commons — Website Updater Service

Receives POST notifications from the catalog listener and keeps
data/models.json on the local repo clone in sync with Cloud SQL.
After patching the file it commits and pushes to GitHub so that
GitHub Pages redeploys with only the changed data (~1-3 min lag).

Endpoints
---------
POST /update               Called by the listener for every real row change.
                           Payload: {"table":"datasets","action":"INSERT","id":42,
                                     "name":"...","updated_at":"..."}
                           - datasets rows: fetch full row from SQL, patch models.json
                           - models rows:   log and skip (models derived in JS from benchmarks)

POST /rebuild              Full regeneration — queries all datasets from SQL, rewrites
                           data/models.json completely, commits and pushes.
                           Use once after seeding, or after any bulk import.

POST /ingest-from-sheets   Full mirror from a Google Sheets CSV export.
                           Auth: Authorization: Bearer <WEBHOOK_SECRET>
                           Body: text/csv (same column layout as the source spreadsheet)
                           Upserts all rows, deletes orphaned rows, rebuilds and pushes.
                           Called automatically by a Google Apps Script onChange trigger.

GET  /                     Health check.

Managed by: /etc/systemd/system/timeseries-updater.service
"""

import csv
import io
import os
import json
import logging
import re
import subprocess
import threading
import time

import psycopg2
import psycopg2.extras
from psycopg2.extras import Json, execute_batch
import requests
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

app = Flask(__name__)

DB_CONN_STR      = os.environ["DB_CONN_STR"]
REPO_LOCAL_PATH  = os.environ["REPO_LOCAL_PATH"]   # e.g. /home/ryangoudjil/Time-Series-Commons
GIT_AUTHOR_NAME  = os.environ.get("GIT_AUTHOR_NAME",  "TimeSeries Updater")
GIT_AUTHOR_EMAIL = os.environ.get("GIT_AUTHOR_EMAIL", "updater@timeseries-commons")
WEBHOOK_SECRET   = os.environ.get("WEBHOOK_SECRET", "")
PORT             = int(os.environ.get("UPDATER_PORT", 8081))

MODELS_JSON_PATH = os.path.join(REPO_LOCAL_PATH, "data", "models.json")

# Serialise all git operations so concurrent POSTs don't race on the file
_git_lock = threading.Lock()


# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(DB_CONN_STR)


def fetch_dataset_row(conn, row_id: int) -> dict | None:
    """Return the full datasets row for the given id, or None."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT id, name, domain, domain_canonical, domain_image,
                      source_url, metadata
               FROM datasets WHERE id = %s""",
            (row_id,)
        )
        return cur.fetchone()


def fetch_all_dataset_rows(conn) -> list:
    """Return all rows from the datasets table ordered by name."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """SELECT id, name, domain, domain_canonical, domain_image,
                      source_url, metadata
               FROM datasets ORDER BY name"""
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Data mapping: SQL row → models.json entry
# ---------------------------------------------------------------------------

def row_to_json_entry(row) -> dict:
    """
    Invert the seed_data.py mapping.

    SQL row columns:
      name, domain, domain_canonical, domain_image, source_url, metadata (JSONB)

    metadata fields stored during seeding / broker ingest:
      slug, timePoints, interval, variables, dimensions,
      description, paperLink, benchmarks

    domain_canonical and domain_image are broker-assigned fields that the
    front-end uses to display the correct domain image card background.
    """
    meta = row["metadata"] or {}
    return {
        "id":               meta.get("slug", ""),
        "name":             row["name"],
        "domain":           row["domain"] or "General",
        "domainCanonical":  row.get("domain_canonical") or "",
        "domainImage":      row.get("domain_image") or "",
        "timePoints":       meta.get("timePoints", "Not specified"),
        "interval":         meta.get("interval",    "Not specified"),
        "variables":        meta.get("variables",   "Not specified"),
        "dimensions":       meta.get("dimensions",  "Not specified"),
        "description":      meta.get("description", ""),
        "dataLink":         row["source_url"] or "",
        "paperLink":        meta.get("paperLink",   ""),
        "benchmarks":       meta.get("benchmarks",  {}),
    }


# ---------------------------------------------------------------------------
# models.json patching
# ---------------------------------------------------------------------------

def load_models_json() -> dict:
    with open(MODELS_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def write_models_json(data: dict) -> None:
    with open(MODELS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info(f"Wrote {len(data.get('models', []))} entries to data/models.json")


def patch_single_entry(entry: dict) -> str:
    """
    Update or insert one entry in models.json.
    Matches on `name` (the stable unique key).
    Returns a short description of what changed.
    """
    data = load_models_json()
    items = data.get("models", [])

    for i, item in enumerate(items):
        if item.get("name") == entry["name"]:
            items[i] = entry
            data["models"] = items
            write_models_json(data)
            return f"updated entry '{entry['name']}'"

    # Not found — append (new INSERT)
    items.append(entry)
    data["models"] = items
    write_models_json(data)
    return f"appended new entry '{entry['name']}'"


def rebuild_full_json(rows: list) -> None:
    """Rewrite models.json entirely from a list of SQL rows."""
    entries = [row_to_json_entry(r) for r in rows]
    write_models_json({"models": entries})


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------

def git_push(commit_message: str) -> None:
    """
    Stage data/models.json, commit, and push to origin.
    All git commands run inside REPO_LOCAL_PATH.
    Raises subprocess.CalledProcessError on failure.
    """
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME":     GIT_AUTHOR_NAME,
        "GIT_AUTHOR_EMAIL":    GIT_AUTHOR_EMAIL,
        "GIT_COMMITTER_NAME":  GIT_AUTHOR_NAME,
        "GIT_COMMITTER_EMAIL": GIT_AUTHOR_EMAIL,
    }

    def run(cmd):
        subprocess.run(cmd, cwd=REPO_LOCAL_PATH, env=env,
                       check=True, capture_output=True, text=True)

    run(["git", "add", "data/models.json"])
    # Skip commit if nothing changed (e.g. duplicate notify)
    result = subprocess.run(
        ["git", "status", "--porcelain", "data/models.json"],
        cwd=REPO_LOCAL_PATH, capture_output=True, text=True
    )
    if not result.stdout.strip():
        log.info("[GIT] Nothing to commit — data/models.json unchanged")
        return

    run(["git", "commit", "-m", commit_message])
    run(["git", "push"])
    log.info(f"[GIT] Pushed: {commit_message}")


# ---------------------------------------------------------------------------
# Google Sheets ingest helpers
# ---------------------------------------------------------------------------

# Columns that carry dataset metadata; every other column is a benchmark model.
_SHEET_METADATA_COLS = {
    'Dataset Name', 'Domain', 'Number of Variables at each time point',
    'Number of Time Points', 'Time interval between points',
    'Primary Source Repository', 'Link to Data', 'Detailed Description',
    'Comments', 'Original Row #', 'Number of Versions', 'Reconciler Version',
    'Reconciler Status', 'Reconciliation Notes',
}


def _clean(v: str | None) -> str | None:
    return v.strip() if v and v.strip() else None


def parse_csv_from_string(csv_text: str) -> list:
    """
    Parse a Google Sheets CSV export into the same list-of-dicts format
    used by scripts/csv_to_json.py and seed_data.py.
    """
    reader = csv.DictReader(io.StringIO(csv_text))
    fieldnames = reader.fieldnames or []
    model_columns = [c for c in fieldnames if c not in _SHEET_METADATA_COLS]

    datasets = []
    for row in reader:
        name = _clean(row.get('Dataset Name'))
        if not name:
            continue

        variables = _clean(row.get('Number of Variables at each time point', ''))
        dimensions = None
        if variables:
            if 'univariate' in variables.lower() or variables == '1' or variables.lower().startswith('1 '):
                dimensions = '1'
            else:
                nums = re.findall(r'\d+', variables)
                if nums:
                    dimensions = nums[0]

        benchmarks = {}
        for col in model_columns:
            val = _clean(row.get(col, ''))
            if val == 'Y':
                benchmarks[col.strip()] = True
            elif val == 'X':
                benchmarks[col.strip()] = False

        datasets.append({
            'id':          name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace(',', ''),
            'name':        name,
            'domain':      _clean(row.get('Domain', '')) or 'General',
            'timePoints':  _clean(row.get('Number of Time Points', '')) or 'Not specified',
            'interval':    _clean(row.get('Time interval between points', '')) or 'Not specified',
            'variables':   variables or 'Not specified',
            'dimensions':  dimensions or 'Not specified',
            'description': _clean(row.get('Detailed Description', '')) or 'No description available.',
            'dataLink':    _clean(row.get('Link to Data', '')) or '',
            'paperLink':   '',
            'benchmarks':  benchmarks,
        })

    return datasets


def upsert_datasets_from_list(cur, datasets: list) -> int:
    """Bulk-upsert a list of parsed dataset dicts. Returns row count."""
    upsert_sql = """
        INSERT INTO datasets (name, domain, source_url, metadata, updated_at)
        VALUES (%(name)s, %(domain)s, %(source_url)s, %(metadata)s, NOW())
        ON CONFLICT (name) DO UPDATE
            SET domain     = EXCLUDED.domain,
                source_url = EXCLUDED.source_url,
                metadata   = EXCLUDED.metadata,
                updated_at = NOW()
    """
    rows = []
    for item in datasets:
        metadata = {
            "slug":        item['id'],
            "timePoints":  item['timePoints'],
            "interval":    item['interval'],
            "variables":   item['variables'],
            "dimensions":  item['dimensions'],
            "description": item['description'],
            "paperLink":   item['paperLink'],
            "benchmarks":  item['benchmarks'],
        }
        rows.append({
            "name":       item['name'],
            "domain":     item['domain'],
            "source_url": item['dataLink'] or None,
            "metadata":   Json(metadata),
        })
    execute_batch(cur, upsert_sql, rows, page_size=200)
    return len(rows)


def delete_orphaned_datasets(cur, datasets: list) -> int:
    """Delete any datasets row whose name is NOT in the incoming list. Returns count."""
    names = [item['name'] for item in datasets]
    cur.execute("DELETE FROM datasets WHERE NOT (name = ANY(%s))", (names,))
    return cur.rowcount


# ---------------------------------------------------------------------------
# Flask endpoints
# ---------------------------------------------------------------------------

@app.route("/")
def health():
    return jsonify({"status": "running", "repo": REPO_LOCAL_PATH}), 200


@app.route("/update", methods=["POST"])
def update():
    """
    Receives a single-row change notification from the listener.
    Patches data/models.json and pushes to GitHub.
    """
    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"error": "empty or non-JSON body"}), 400

    table  = payload.get("table")
    action = payload.get("action")
    row_id = payload.get("id")
    name   = payload.get("name", "")

    log.info(f"[UPDATE] table={table} action={action} id={row_id} name={name!r}")

    if table != "datasets":
        log.info(f"[SKIP] table={table} — only datasets affect models.json")
        return jsonify({"status": "skipped", "reason": "table not datasets"}), 200

    # Handle DELETE: remove the entry from models.json by name
    if action == "DELETE":
        if not name:
            log.warning("[UPDATE] DELETE received with no name — skipping")
            return jsonify({"status": "skipped", "reason": "missing name for DELETE"}), 200

        with _git_lock:
            try:
                data  = load_models_json()
                items = data.get("models", [])
                before = len(items)
                items  = [m for m in items if m.get("name") != name]
                if len(items) == before:
                    log.info(f"[UPDATE] DELETE — '{name}' not found in JSON, nothing to remove")
                    return jsonify({"status": "skipped", "reason": "not in JSON"}), 200
                data["models"] = items
                write_models_json(data)
                git_push(f"auto: removed '{name}' [DELETE]")
            except Exception as e:
                log.error(f"[UPDATE] DELETE patch/push failed: {e}")
                return jsonify({"error": str(e)}), 500

        log.info(f"[OK] Removed '{name}' from models.json — pushed to GitHub")
        return jsonify({"status": "ok", "change": f"removed '{name}'"}), 200

    # INSERT / UPDATE: fetch the full row and patch models.json
    try:
        conn = get_connection()
        try:
            row = fetch_dataset_row(conn, row_id)
        finally:
            conn.close()
    except Exception as e:
        log.error(f"[UPDATE] DB fetch failed: {e}")
        return jsonify({"error": str(e)}), 500

    if row is None:
        log.warning(f"[UPDATE] Row id={row_id} not found in datasets — skipping")
        return jsonify({"status": "skipped", "reason": "row not found"}), 200

    entry = row_to_json_entry(row)

    with _git_lock:
        try:
            change_desc = patch_single_entry(entry)
            git_push(f"auto: {change_desc} [{action}]")
        except Exception as e:
            log.error(f"[UPDATE] Patch/push failed: {e}")
            return jsonify({"error": str(e)}), 500

    log.info(f"[OK] {change_desc} — pushed to GitHub")
    return jsonify({"status": "ok", "change": change_desc}), 200


@app.route("/rebuild", methods=["POST"])
def rebuild():
    """
    Full regeneration: queries all datasets from SQL, rewrites
    data/models.json, commits and pushes.

    Call this:
      - Once after running seed_data.py for the first time
      - After any bulk import or manual SQL edit
    """
    log.info("[REBUILD] Starting full regeneration of data/models.json ...")

    try:
        conn = get_connection()
        try:
            rows = fetch_all_dataset_rows(conn)
        finally:
            conn.close()
    except Exception as e:
        log.error(f"[REBUILD] DB fetch failed: {e}")
        return jsonify({"error": str(e)}), 500

    with _git_lock:
        try:
            rebuild_full_json(rows)
            git_push(f"auto: full rebuild from SQL ({len(rows)} datasets)")
        except Exception as e:
            log.error(f"[REBUILD] Write/push failed: {e}")
            return jsonify({"error": str(e)}), 500

    log.info(f"[REBUILD] Done — {len(rows)} datasets pushed to GitHub")
    return jsonify({"status": "ok", "datasets_written": len(rows)}), 200


@app.route("/ingest-from-sheets", methods=["POST"])
def ingest_from_sheets():
    """
    Receives a full CSV export from Google Sheets (via Apps Script onChange trigger).
    Performs a full mirror against the datasets table:
      1. Upsert every row found in the CSV.
      2. Delete any datasets row whose name is not present in the CSV.
      3. Rebuild data/models.json and push to GitHub directly (the schema DELETE
         trigger does not fire pg_notify, so we bypass the listener here).

    Auth:    Authorization: Bearer <WEBHOOK_SECRET>
    Body:    text/csv  (same column layout as the source spreadsheet)
    Returns: {"status":"ok","upserted":N,"deleted":M}
    """
    auth = request.headers.get("Authorization", "")
    if not WEBHOOK_SECRET or auth != f"Bearer {WEBHOOK_SECRET}":
        log.warning("[INGEST] Rejected — bad or missing Authorization header")
        return jsonify({"error": "unauthorized"}), 401

    csv_text = request.get_data(as_text=True)
    if not csv_text.strip():
        return jsonify({"error": "empty body"}), 400

    log.info("[INGEST] Received CSV payload, parsing ...")
    try:
        datasets = parse_csv_from_string(csv_text)
    except Exception as e:
        log.error(f"[INGEST] CSV parse failed: {e}")
        return jsonify({"error": f"CSV parse error: {e}"}), 400

    if not datasets:
        return jsonify({"error": "no datasets found in CSV"}), 400

    log.info(f"[INGEST] Parsed {len(datasets)} datasets from sheet")

    try:
        conn = get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    n_upserted = upsert_datasets_from_list(cur, datasets)
                    n_deleted  = delete_orphaned_datasets(cur, datasets)
        finally:
            conn.close()
    except Exception as e:
        log.error(f"[INGEST] DB operation failed: {e}")
        return jsonify({"error": str(e)}), 500

    log.info(f"[INGEST] DB synced — upserted={n_upserted} deleted={n_deleted}")

    # Rebuild and push directly: pg_notify only fires for INSERT/UPDATE, not DELETE,
    # so we cannot rely on the listener chain when rows have been removed.
    with _git_lock:
        try:
            conn = get_connection()
            try:
                rows = fetch_all_dataset_rows(conn)
            finally:
                conn.close()
            rebuild_full_json(rows)
            git_push(
                f"auto: sheets sync ({n_upserted} upserted, {n_deleted} deleted, "
                f"{len(rows)} total)"
            )
        except Exception as e:
            log.error(f"[INGEST] Rebuild/push failed: {e}")
            return jsonify({"error": str(e)}), 500

    log.info("[INGEST] Done — pushed to GitHub")
    return jsonify({"status": "ok", "upserted": n_upserted, "deleted": n_deleted}), 200


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info(f"Website updater starting on port {PORT}")
    log.info(f"Repo path : {REPO_LOCAL_PATH}")
    log.info(f"JSON path : {MODELS_JSON_PATH}")
    app.run(host="0.0.0.0", port=PORT)
