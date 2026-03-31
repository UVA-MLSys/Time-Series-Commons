"""
Time Series Commons — Catalog Broker Service

Acts as the "Events Publisher" layer between external producers (DeepCollector,
scripts, manual tooling) and PostgreSQL. Replaces the Google Sheets → Apps Script
→ /ingest-from-sheets path with a direct, authenticated JSON API.

Architecture mirrors the IndyCar-master pub/sub pattern:
  Producer (DeepCollector) → Broker (this service)   ≈ Race log → Events Publisher
  Broker → PostgreSQL UPSERT                          ≈ Publisher → ActiveMQ Apollo
  pg_notify → catalog_datasets / catalog_models       ≈ MQTT per-car topics
  Listener picks up NOTIFY → Updater → JSON + git     ≈ Storm spout → Socket server

Endpoints
---------
GET  /health                  Liveness check.
POST /ingest                  Upsert or delete a single dataset or model record.
POST /ingest/batch            Bulk upsert / delete for DeepCollector batch runs.

Authentication
--------------
All POST endpoints require:    Authorization: Bearer <BROKER_SECRET>

Domain Enrichment
-----------------
Before every write the broker resolves the raw `domain` field into a canonical
domain name and image path using DomainResolver (backed by data/domain-config.json).
DeepCollector only needs to supply the raw domain string — no manual tagging needed.

Environment Variables
---------------------
DB_CONN_STR          PostgreSQL connection string (via Cloud SQL Auth Proxy or direct)
BROKER_SECRET        Shared secret for bearer token auth
DOMAIN_CONFIG_PATH   Absolute path to data/domain-config.json
BROKER_PORT          HTTP port (default 8083)

Managed by: /etc/systemd/system/timeseries-broker.service
"""

import json
import logging
import os
from typing import Any

import psycopg2
import psycopg2.extras
from psycopg2.extras import Json
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from domain_resolver import DomainResolver

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_CONN_STR        = os.environ["DB_CONN_STR"]
BROKER_SECRET      = os.environ["BROKER_SECRET"]
DOMAIN_CONFIG_PATH = os.environ["DOMAIN_CONFIG_PATH"]
PORT               = int(os.environ.get("BROKER_PORT", 8083))

# ---------------------------------------------------------------------------
# Domain resolver (loaded once at startup)
# ---------------------------------------------------------------------------

resolver = DomainResolver(DOMAIN_CONFIG_PATH)

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Time Series Commons — Catalog Broker",
    description=(
        "Authenticated ingestion endpoint. DeepCollector (or any producer) "
        "POSTs records here; the broker enriches them with canonical domain + "
        "image, writes to PostgreSQL, and fires pg_notify so downstream "
        "services can react in real time."
    ),
    version="1.0.0",
)

bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def require_auth(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> None:
    if credentials.credentials != BROKER_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token.",
        )


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class IngestRecord(BaseModel):
    """
    A single dataset or model record to upsert or delete.

    For datasets:
      Required: name
      Optional: domain, source_url, metadata (dict matching the datasets schema)

    For models:
      Required: name
      Optional: architecture, domain (derived from metadata.dominantDomain if omitted),
                source_url, metadata
    """

    table:      str              = Field(..., pattern=r"^(datasets|models)$",
                                         description="'datasets' or 'models'")
    action:     str              = Field("UPSERT", pattern=r"^(UPSERT|DELETE)$",
                                         description="'UPSERT' (default) or 'DELETE'")
    record:     dict[str, Any]   = Field(..., description="Row fields (see schema.sql)")


class BatchIngestRequest(BaseModel):
    records: list[IngestRecord] = Field(..., min_length=1,
                                         description="List of records to process in order")


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(DB_CONN_STR)


def _enrich_record(record: dict, table: str) -> dict:
    """
    Resolve raw domain text → canonical domain + image and inject into record.

    For datasets the domain field is 'domain'.
    For models it may be 'domain' or fall back to metadata.dominantDomain.
    """
    raw_domain = record.get("domain", "")

    if not raw_domain and table == "models":
        raw_domain = (record.get("metadata") or {}).get("dominantDomain", "")

    result = resolver.resolve(raw_domain)
    record["domain_canonical"] = result["canonical"]
    record["domain_image"]     = result["image"]
    return record


def _upsert_dataset(cur, record: dict) -> str:
    cur.execute(
        """
        INSERT INTO datasets
            (name, domain, domain_canonical, domain_image, source_url, metadata, updated_at)
        VALUES
            (%(name)s, %(domain)s, %(domain_canonical)s, %(domain_image)s,
             %(source_url)s, %(metadata)s, NOW())
        ON CONFLICT (name) DO UPDATE
            SET domain           = EXCLUDED.domain,
                domain_canonical = EXCLUDED.domain_canonical,
                domain_image     = EXCLUDED.domain_image,
                source_url       = EXCLUDED.source_url,
                metadata         = EXCLUDED.metadata,
                updated_at       = NOW()
        RETURNING id, (xmax = 0) AS inserted
        """,
        {
            "name":             record.get("name"),
            "domain":           record.get("domain"),
            "domain_canonical": record["domain_canonical"],
            "domain_image":     record["domain_image"],
            "source_url":       record.get("source_url"),
            "metadata":         Json(record["metadata"]) if record.get("metadata") else None,
        },
    )
    row = cur.fetchone()
    return "inserted" if row and row[1] else "updated"


def _upsert_model(cur, record: dict) -> str:
    cur.execute(
        """
        INSERT INTO models
            (name, architecture, domain_canonical, domain_image, source_url, metadata, updated_at)
        VALUES
            (%(name)s, %(architecture)s, %(domain_canonical)s, %(domain_image)s,
             %(source_url)s, %(metadata)s, NOW())
        ON CONFLICT (name) DO UPDATE
            SET architecture     = EXCLUDED.architecture,
                domain_canonical = EXCLUDED.domain_canonical,
                domain_image     = EXCLUDED.domain_image,
                source_url       = EXCLUDED.source_url,
                metadata         = EXCLUDED.metadata,
                updated_at       = NOW()
        RETURNING id, (xmax = 0) AS inserted
        """,
        {
            "name":             record.get("name"),
            "architecture":     record.get("architecture"),
            "domain_canonical": record["domain_canonical"],
            "domain_image":     record["domain_image"],
            "source_url":       record.get("source_url"),
            "metadata":         Json(record["metadata"]) if record.get("metadata") else None,
        },
    )
    row = cur.fetchone()
    return "inserted" if row and row[1] else "updated"


def _delete_record(cur, table: str, name: str) -> int:
    cur.execute(f"DELETE FROM {table} WHERE name = %s", (name,))
    return cur.rowcount


def _process_one(cur, item: IngestRecord) -> dict:
    """
    Process a single IngestRecord inside an already-open cursor/transaction.
    Returns a result dict suitable for the API response.
    """
    record = dict(item.record)
    table  = item.table
    action = item.action.upper()

    if not record.get("name"):
        raise ValueError("record.name is required")

    if action == "DELETE":
        deleted = _delete_record(cur, table, record["name"])
        return {
            "name":   record["name"],
            "table":  table,
            "action": "DELETE",
            "status": "deleted" if deleted else "not_found",
        }

    # UPSERT path — enrich with domain info first
    record = _enrich_record(record, table)

    if table == "datasets":
        op = _upsert_dataset(cur, record)
    else:
        op = _upsert_model(cur, record)

    return {
        "name":             record["name"],
        "table":            table,
        "action":           "UPSERT",
        "status":           op,
        "domain_canonical": record["domain_canonical"],
        "domain_image":     record["domain_image"],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Liveness check — confirms the broker is running and the domain config loaded."""
    return {
        "status":          "running",
        "port":            PORT,
        "canonical_domains": resolver.canonical_names(),
    }


@app.post("/ingest", dependencies=[Depends(require_auth)])
def ingest(item: IngestRecord):
    """
    Upsert or delete a single dataset or model.

    The broker resolves the raw `domain` field to a canonical domain and image
    before writing to PostgreSQL. The DB trigger fires pg_notify on both
    'catalog_updates' and 'catalog_<table>' channels so the listener reacts
    immediately.

    Example body:
    ```json
    {
      "table": "datasets",
      "action": "UPSERT",
      "record": {
        "name": "M3 Competition",
        "domain": "Economics",
        "source_url": "https://...",
        "metadata": { "timePoints": "3000", "interval": "Monthly", ... }
      }
    }
    ```
    """
    try:
        conn = get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    result = _process_one(cur, item)
        finally:
            conn.close()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        log.error("[INGEST] Failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    log.info(
        "[INGEST] %s/%s → %s  (domain_canonical=%s)",
        item.table, item.record.get("name"), result["status"],
        result.get("domain_canonical", "—"),
    )
    return result


@app.post("/ingest/batch", dependencies=[Depends(require_auth)])
def ingest_batch(body: BatchIngestRequest):
    """
    Bulk upsert / delete — processes all records in a single transaction.

    Intended for DeepCollector batch discovery runs. If any record fails
    validation (e.g. missing name), the entire batch is rolled back.

    Returns per-record results along with a summary count.
    """
    results = []
    try:
        conn = get_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    for item in body.records:
                        r = _process_one(cur, item)
                        results.append(r)
        finally:
            conn.close()
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        log.error("[INGEST/BATCH] Failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    inserted = sum(1 for r in results if r["status"] == "inserted")
    updated  = sum(1 for r in results if r["status"] == "updated")
    deleted  = sum(1 for r in results if r["status"] == "deleted")

    log.info(
        "[INGEST/BATCH] %d total — inserted=%d updated=%d deleted=%d",
        len(results), inserted, updated, deleted,
    )
    return {
        "status":   "ok",
        "total":    len(results),
        "inserted": inserted,
        "updated":  updated,
        "deleted":  deleted,
        "results":  results,
    }


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    log.info("Catalog Broker starting on port %d", PORT)
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="info")
