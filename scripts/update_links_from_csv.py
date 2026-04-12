#!/usr/bin/env python3
"""
update_links_from_csv.py — Targeted link update from CSV → models.json + PostgreSQL

Reads the "Link to Data" column from the combined CSV and updates:
  1. data/models.json  — the `dataLink` field for each matching dataset entry
  2. datasets.source_url in PostgreSQL — via UPDATE … WHERE name = …

Only source_url / dataLink are touched; all other fields are left untouched.

Link classification:
  - http:// or https:// prefix  → used as-is
  - DOI: <id> prefix             → normalised to https://doi.org/<id>
  - anything else (placeholder,  → stored as None / NULL
    "No link available", empty)

Usage (from repo root):
    DB_CONN_STR="postgresql://ts_user:PASSWORD@127.0.0.1:5432/timeseries_db" \\
        python scripts/update_links_from_csv.py

Safe to re-run — idempotent UPDATE with ON CONFLICT-free targeting.
"""

import csv
import json
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
CSV_PATH  = REPO_ROOT / "Time-Series Common_Data_1-5-2026_COMBINED2 - Combinedv10.csv"
JSON_PATH = REPO_ROOT / "data" / "models.json"


# ---------------------------------------------------------------------------
# Link classification
# ---------------------------------------------------------------------------
_DOI_RE = re.compile(r"^DOI:\s*(.+)$", re.IGNORECASE)


def classify_link(raw: Optional[str]) -> Optional[str]:
    """
    Return a canonical URL string, or None if the value is not a usable link.

    Rules:
      - http:// / https:// → returned as-is (stripped)
      - DOI: <id>          → https://doi.org/<id>
      - everything else    → None
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
# models.json update
# ---------------------------------------------------------------------------
def update_models_json(json_path: Path, links: Dict[str, Optional[str]]) -> dict:
    """
    Patch the `dataLink` field for each entry in models.json.

    Returns a stats dict: {updated, unchanged, not_in_json}.
    """
    with open(json_path, encoding="utf-8") as fh:
        data = json.load(fh)

    entries = data.get("models", [])
    name_to_entry = {e.get("name", ""): e for e in entries}

    stats = {"updated": 0, "unchanged": 0, "not_in_json": 0}

    for name, link in links.items():
        entry = name_to_entry.get(name)
        if entry is None:
            stats["not_in_json"] += 1
            continue

        current = entry.get("dataLink") or None
        new_val  = link or ""

        if current == new_val or (not current and not new_val):
            stats["unchanged"] += 1
        else:
            entry["dataLink"] = new_val
            stats["updated"] += 1

    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return stats


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
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    # ── Validate inputs ────────────────────────────────────────────────────
    if not CSV_PATH.exists():
        log.error("CSV not found: %s", CSV_PATH)
        sys.exit(1)

    if not JSON_PATH.exists():
        log.error("models.json not found: %s", JSON_PATH)
        sys.exit(1)

    db_conn_str = os.environ.get("DB_CONN_STR")

    # ── Parse CSV ──────────────────────────────────────────────────────────
    log.info("Parsing CSV: %s", CSV_PATH)
    links = parse_csv_links(CSV_PATH)
    log.info("  %d dataset rows found in CSV", len(links))

    real_urls    = sum(1 for v in links.values() if v and not v.startswith("https://doi.org/"))
    doi_urls     = sum(1 for v in links.values() if v and v.startswith("https://doi.org/"))
    no_link      = sum(1 for v in links.values() if not v)
    log.info("  %d real URLs  |  %d DOI-normalised  |  %d no usable link",
             real_urls, doi_urls, no_link)

    # ── Update models.json ─────────────────────────────────────────────────
    log.info("Updating data/models.json …")
    json_stats = update_models_json(JSON_PATH, links)
    log.info(
        "  models.json — updated: %d  |  unchanged: %d  |  not in JSON: %d",
        json_stats["updated"], json_stats["unchanged"], json_stats["not_in_json"],
    )

    # ── Update PostgreSQL ──────────────────────────────────────────────────
    if not db_conn_str:
        log.warning(
            "DB_CONN_STR not set — skipping database update. "
            "models.json has already been written."
        )
        log.warning(
            "To update the DB, re-run with: "
            'DB_CONN_STR="postgresql://..." python scripts/update_links_from_csv.py'
        )
        return

    log.info("Connecting to PostgreSQL …")
    db_stats = update_database(db_conn_str, links)
    log.info(
        "  database — updated: %d  |  not found: %d  |  DOI-normalised: %d",
        db_stats["updated"], db_stats["not_found"], db_stats["doi_normalised"],
    )

    # ── Summary ────────────────────────────────────────────────────────────
    log.info("Done.")
    log.info("─" * 60)
    log.info("  CSV rows parsed           : %d", len(links))
    log.info("  URLs (real)               : %d", real_urls)
    log.info("  URLs (DOI-normalised)     : %d", doi_urls)
    log.info("  No usable link (→ NULL)   : %d", no_link)
    log.info("  models.json updated       : %d", json_stats["updated"])
    log.info("  DB rows updated           : %d", db_stats["updated"])
    log.info("  DB rows not found         : %d", db_stats["not_found"])


if __name__ == "__main__":
    main()
