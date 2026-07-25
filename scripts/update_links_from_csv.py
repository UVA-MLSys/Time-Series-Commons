#!/usr/bin/env python3
"""
update_links_from_csv.py — Targeted link update from CSV → PostgreSQL

Reads the "Link to Data" column from CSVwithcorrectedlinks.csv and updates:
  1. datasets.source_url in PostgreSQL — via UPDATE … WHERE name = …

Only real, clickable URLs are stored (http/https or DOI-normalised).
Plain-text values (e.g. "Adiac Description", "Link") are treated as no link
and written as NULL, preventing broken relative-URL navigation on the site.

The DB UPDATE fires pg_notify on every row, which drives the pipeline:
  listener → updater → models.json patch → git push → GitHub Pages redeploy

Optionally, set UPDATER_URL to force an immediate full rebuild after all
DB updates complete (e.g. UPDATER_URL=http://localhost:8081).

Usage (from repo root):
    DB_CONN_STR="postgresql://ts_user:PASSWORD@127.0.0.1:5432/timeseries_db" \\
        python scripts/update_links_from_csv.py

    # With forced rebuild:
    DB_CONN_STR="..." UPDATER_URL="http://localhost:8081" \\
        python scripts/update_links_from_csv.py

Safe to re-run — idempotent UPDATE with ON CONFLICT-free targeting.
"""

import csv
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH  = REPO_ROOT / "CSVwithcorrectedlinks.csv"


# ---------------------------------------------------------------------------
# Link classification
# ---------------------------------------------------------------------------
_DOI_RE = re.compile(r"^DOI:\s*(.+)$", re.IGNORECASE)


def classify_link(raw: Optional[str]) -> Optional[str]:
    """
    Return a normalised, clickable URL or None.

    Rules:
      - http:// / https:// → returned as-is (stripped)
      - DOI: <id>          → https://doi.org/<id>
      - any other text     → None  (plain-text values like "Adiac Description"
                             or "Link" are not valid hrefs and must not be stored)
      - empty / None       → None
    """
    if not raw:
        return None
    value = raw.strip()
    if not value:
        return None

    if value.lower().startswith("http://") or value.lower().startswith("https://"):
        return value

    m = _DOI_RE.match(value)
    if m:
        doi_id = m.group(1).strip()
        return f"https://doi.org/{doi_id}"

    # Plain text (e.g. "Adiac Description", "Link", "Zenodo Record") → no link.
    return None


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------
def parse_csv_links(csv_path: Path) -> Dict[str, Optional[str]]:
    """
    Return a mapping of  dataset_name → classified_link  for every row in
    the CSV that has a non-empty "Dataset Name".
    """
    links: Dict[str, Optional[str]] = {}

    with open(csv_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = (row.get("Dataset Name") or "").strip()
            if not name:
                continue
            raw_link = (row.get("Link to Data") or "").strip()
            links[name] = classify_link(raw_link)

    return links


# ---------------------------------------------------------------------------
# PostgreSQL update
# ---------------------------------------------------------------------------
def update_database(conn_str: str, links: Dict[str, Optional[str]]) -> dict:
    """
    Issue UPDATE datasets SET source_url = %s, updated_at = NOW() WHERE name = %s
    for every entry in *links*.

    Returns a stats dict: {updated, not_found, doi_normalised}.
    """
    try:
        import psycopg2
        from psycopg2.extras import execute_batch
    except ImportError:
        log.error("psycopg2-binary not installed. Run: pip install psycopg2-binary")
        sys.exit(1)

    conn = psycopg2.connect(conn_str)
    stats = {"updated": 0, "not_found": 0, "doi_normalised": 0}

    try:
        with conn:
            with conn.cursor() as cur:
                for name, link in links.items():
                    # Check whether the row exists first so we can distinguish
                    # "not found" from a genuine update.
                    cur.execute("SELECT source_url FROM datasets WHERE name = %s", (name,))
                    row = cur.fetchone()

                    if row is None:
                        stats["not_found"] += 1
                        continue

                    cur.execute(
                        "UPDATE datasets SET source_url = %s, updated_at = NOW() WHERE name = %s",
                        (link, name),
                    )
                    stats["updated"] += 1

                    if link and link.startswith("https://doi.org/"):
                        stats["doi_normalised"] += 1
    finally:
        conn.close()

    return stats


# ---------------------------------------------------------------------------
# Updater integration
# ---------------------------------------------------------------------------
def trigger_rebuild(updater_url: str) -> None:
    """POST to the updater /rebuild endpoint to force a full models.json regeneration."""
    try:
        import urllib.request
        url = updater_url.rstrip("/") + "/rebuild"
        req = urllib.request.Request(url, method="POST", data=b"")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
        log.info("  /rebuild → HTTP %d  %s", resp.status, body[:120])
    except Exception as exc:
        log.warning("  /rebuild failed (non-fatal): %s", exc)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # ── Validate inputs ────────────────────────────────────────────────────
    if not CSV_PATH.exists():
        log.error("CSV not found: %s", CSV_PATH)
        sys.exit(1)

    db_conn_str  = os.environ.get("DB_CONN_STR")
    updater_url  = os.environ.get("UPDATER_URL")

    if not db_conn_str:
        log.error(
            "DB_CONN_STR not set. Run with:\n"
            '  DB_CONN_STR="postgresql://ts_user:PASSWORD@127.0.0.1:5432/timeseries_db" '
            "python scripts/update_links_from_csv.py"
        )
        sys.exit(1)

    # ── Parse CSV ──────────────────────────────────────────────────────────
    log.info("Parsing CSV: %s", CSV_PATH)
    links = parse_csv_links(CSV_PATH)
    log.info("  %d dataset rows found in CSV", len(links))

    real_urls  = sum(1 for v in links.values() if v and v.startswith("http"))
    doi_urls   = sum(1 for v in links.values() if v and v.startswith("https://doi.org/"))
    no_link    = sum(1 for v in links.values() if not v)
    log.info("  %d real URLs  |  %d DOI-normalised  |  %d empty/text → NULL",
             real_urls, doi_urls, no_link)

    # ── Update PostgreSQL ──────────────────────────────────────────────────
    log.info("Connecting to PostgreSQL …")
    db_stats = update_database(db_conn_str, links)
    log.info(
        "  database — updated: %d  |  not found: %d  |  DOI-normalised: %d",
        db_stats["updated"], db_stats["not_found"], db_stats["doi_normalised"],
    )

    # ── Optional: force immediate rebuild via updater service ──────────────
    if updater_url:
        log.info("Triggering full rebuild via updater at %s …", updater_url)
        trigger_rebuild(updater_url)
    else:
        log.info(
            "Tip: set UPDATER_URL=http://localhost:8081 to trigger an immediate "
            "rebuild instead of relying on per-row pg_notify events."
        )

    # ── Summary ────────────────────────────────────────────────────────────
    log.info("Done.")
    log.info("─" * 60)
    log.info("  CSV rows parsed           : %d", len(links))
    log.info("  URLs (real + DOI)         : %d", real_urls)
    log.info("  Empty / text → NULL       : %d", no_link)
    log.info("  DB rows updated           : %d", db_stats["updated"])
    log.info("  DB rows not found         : %d", db_stats["not_found"])


if __name__ == "__main__":
    main()
