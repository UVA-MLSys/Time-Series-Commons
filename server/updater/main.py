"""
Time Series Commons — Website Updater Service

Receives POST notifications from the catalog listener and keeps
data/models.json on the local repo clone in sync with Cloud SQL.
After patching the file it commits and pushes to GitHub so that
GitHub Pages redeploys with only the changed data (~1-3 min lag).

Endpoints
---------
POST /update   Called by the listener for every real row change.
               Payload: {"table":"datasets","action":"INSERT","id":42,
                         "name":"...","updated_at":"..."}
               - datasets rows: fetch full row from SQL, patch models.json
               - models rows:   log and skip (models derived in JS from benchmarks)

POST /rebuild  Full regeneration — queries all datasets from SQL, rewrites
               data/models.json completely, commits and pushes.
               Use once after seeding, or after any bulk import.

GET  /         Health check.

Managed by: /etc/systemd/system/timeseries-updater.service
"""

import os
import json
import logging
import subprocess
import threading
import time

import psycopg2
import psycopg2.extras
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

DB_CONN_STR    = os.environ["DB_CONN_STR"]
REPO_LOCAL_PATH = os.environ["REPO_LOCAL_PATH"]   # e.g. /home/ryangoudjil/Time-Series-Commons
GIT_AUTHOR_NAME  = os.environ.get("GIT_AUTHOR_NAME",  "TimeSeries Updater")
GIT_AUTHOR_EMAIL = os.environ.get("GIT_AUTHOR_EMAIL", "updater@timeseries-commons")
PORT = int(os.environ.get("UPDATER_PORT", 8081))

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
            "SELECT id, name, domain, source_url, metadata FROM datasets WHERE id = %s",
            (row_id,)
        )
        return cur.fetchone()


def fetch_all_dataset_rows(conn) -> list:
    """Return all rows from the datasets table ordered by name."""
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT id, name, domain, source_url, metadata FROM datasets ORDER BY name"
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Data mapping: SQL row → models.json entry
# ---------------------------------------------------------------------------

def row_to_json_entry(row) -> dict:
    """
    Invert the seed_data.py mapping.

    SQL row columns:
      name, domain, source_url, metadata (JSONB)

    metadata fields stored during seeding:
      slug, timePoints, interval, variables, dimensions,
      description, paperLink, benchmarks
    """
    meta = row["metadata"] or {}
    return {
        "id":          meta.get("slug", ""),
        "name":        row["name"],
        "domain":      row["domain"] or "General",
        "timePoints":  meta.get("timePoints", "Not specified"),
        "interval":    meta.get("interval",    "Not specified"),
        "variables":   meta.get("variables",   "Not specified"),
        "dimensions":  meta.get("dimensions",  "Not specified"),
        "description": meta.get("description", ""),
        "dataLink":    row["source_url"] or "",
        "paperLink":   meta.get("paperLink",   ""),
        "benchmarks":  meta.get("benchmarks",  {}),
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


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    log.info(f"Website updater starting on port {PORT}")
    log.info(f"Repo path : {REPO_LOCAL_PATH}")
    log.info(f"JSON path : {MODELS_JSON_PATH}")
    app.run(host="0.0.0.0", port=PORT)
