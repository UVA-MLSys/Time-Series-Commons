"""
Seed the database from data/models.json.

Usage (run from the repo root on the VM after the DB is up):
    cd ~/Time-Series-Commons
    python3 server/scripts/seed_from_json.py

Requires:
    pip install psycopg2-binary python-dotenv

Reads DB_CONN_STR from server/listener/.env (or SERVER_LISTENER_ENV env var).
The domain_canonical / domain_image columns are filled in by domain_resolver.
"""

import json
import os
import sys
from pathlib import Path

# ── locate repo root ──────────────────────────────────────────────────────────
REPO = Path(__file__).resolve().parents[2]

# ── import domain_resolver from server/broker ─────────────────────────────────
sys.path.insert(0, str(REPO / "server" / "broker"))
from domain_resolver import DomainResolver

resolver = DomainResolver(REPO / "data" / "domain-config.json")

# ── load DB connection string ─────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(REPO / "server" / "listener" / ".env")

DB_CONN = os.environ.get("DB_CONN_STR")
if not DB_CONN:
    sys.exit("ERROR: DB_CONN_STR not set. Check server/listener/.env")

# ── load data ─────────────────────────────────────────────────────────────────
with open(REPO / "data" / "models.json") as f:
    records = json.load(f)["models"]

print(f"Loaded {len(records)} records from data/models.json")

# ── connect ───────────────────────────────────────────────────────────────────
import psycopg2
conn = psycopg2.connect(DB_CONN)
conn.autocommit = False
cur = conn.cursor()

upserted = 0
skipped  = 0

for rec in records:
    name = rec.get("name", "").strip()
    if not name:
        skipped += 1
        continue

    domain_raw = rec.get("domain", "")
    resolved   = resolver.resolve(domain_raw)

    metadata = {
        "slug":        rec.get("id", ""),
        "timePoints":  rec.get("timePoints", ""),
        "interval":    rec.get("interval", ""),
        "variables":   rec.get("variables", ""),
        "dimensions":  rec.get("dimensions", ""),
        "description": rec.get("description", ""),
        "dataLink":    rec.get("dataLink", ""),
        "paperLink":   rec.get("paperLink", ""),
        "benchmarks":  rec.get("benchmarks", {}),
    }

    cur.execute(
        """
        INSERT INTO datasets
            (name, domain, domain_canonical, domain_image, source_url, metadata)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (name) DO UPDATE SET
            domain           = EXCLUDED.domain,
            domain_canonical = EXCLUDED.domain_canonical,
            domain_image     = EXCLUDED.domain_image,
            source_url       = EXCLUDED.source_url,
            metadata         = EXCLUDED.metadata,
            updated_at       = NOW()
        """,
        (
            name,
            domain_raw,
            resolved["canonical"],
            resolved["image"],
            rec.get("dataLink", ""),
            json.dumps(metadata),
        ),
    )
    upserted += 1

conn.commit()
cur.close()
conn.close()

print(f"Done — {upserted} upserted, {skipped} skipped (no name).")
