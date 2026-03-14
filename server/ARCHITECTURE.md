# Time Series Commons — Real-Time Catalog Update Engine

## Architecture, Design Rationale, and Implementation

**Project:** Time Series Commons  
**Institution:** University of Virginia, Machine Learning Systems (UVA-MLSys) Research Group  
**Principal Investigator:** Dr. Judy Fox  
**Infrastructure Provider:** Google Cloud Platform  

---

## 1. Overview

The Time Series Commons is a curated, living catalog of AI time series datasets, models, and benchmarks — a community-maintained registry analogous to HuggingFace but specialized for time series analysis. The catalog currently indexes 790+ unique datasets and 78+ benchmark models, discovered and documented by an agentic LLM pipeline called DeepCollector.

This document describes the real-time catalog update engine that replaces a manual Google Sheets workflow with a production-grade, event-driven pipeline. The system ensures that the public-facing website always reflects the latest catalog state within approximately two minutes of any database change, with minimal compute overhead and no full-site rebuilds.

---

## 2. Design Inspiration: The IndyCar Anomaly Detection Model

The architecture of this engine is directly inspired by the streaming anomaly detection system described in:

> Vance, N., et al. *"Anomaly Detection over Streaming Data: Indy500 Case Study."* Indiana University. 

In that system, telemetry sensors on 33 IndyCar race vehicles generated continuous streams of speed, RPM, throttle, and fuel data. An MQTT broker (Apache Apollo) acted as the publish/subscribe message layer between the sensor data stream and an Apache Storm processing topology. Apache Storm consumed messages and passed them through HTM (Hierarchical Temporal Memory) neural networks. Critically, **only anomalous events triggered downstream responses** — the system did not reprocess all 4.8 million historical records on each sensor reading.

The Time Series Commons engine maps directly onto this architecture:

| IndyCar Component | Time Series Commons Equivalent |
|---|---|
| TCP sensor stream (33 cars) | DeepCollector writing rows to Cloud SQL |
| MQTT broker (Apache Apollo) | PostgreSQL `LISTEN`/`NOTIFY` pub/sub channel |
| Apache Storm topology | Python listener server (`timeseries-listener`) |
| HTM anomaly filter | Row hash diff engine (`site_state` dictionary) |
| Storm bolt downstream action | REST `POST` to website updater endpoint |
| MongoDB persistence layer | Google Cloud SQL as source of truth |
| WebSocket broadcast to dashboard | Git commit + push to GitHub Pages |

**The key design principle inherited from the IndyCar system:** react only to what changed, never reprocess everything. The hash diff gate is the direct analog of the HTM anomaly filter — it absorbs the vast majority of redundant signals and only propagates genuine state transitions downstream.

---

## 3. System Architecture

### 3.1 High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                 │
│                                                                     │
│  DeepCollector (LLM agent)          Manual curator / researcher     │
│  ┌─────────────────────┐            ┌──────────────────────────┐   │
│  │ Scrapes web, papers,│            │ Direct psql INSERT/UPDATE│   │
│  │ repos → structured  │            │ via Cloud SQL public IP  │   │
│  │ metadata            │            │ (sslmode=require)        │   │
│  └──────────┬──────────┘            └────────────┬─────────────┘   │
│             │                                    │                  │
│             └──────────────┬───────────────────┘                   │
│                            ▼                                        │
│              ON CONFLICT (name) DO UPDATE upsert                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    GOOGLE CLOUD SQL (PostgreSQL 18)                 │
│                    Instance: free-trial-first-project               │
│                    Region: us-east4-a                               │
│                                                                     │
│  ┌────────────────────┐    ┌─────────────────────────────────────┐ │
│  │ datasets table     │    │ models table                        │ │
│  │ 790 rows           │    │ 78 rows                             │ │
│  │ name (UNIQUE)      │    │ name (UNIQUE)                       │ │
│  │ domain             │    │ architecture                        │ │
│  │ source_url         │    │ source_url                          │ │
│  │ metadata (JSONB)   │    │ metadata (JSONB)                    │ │
│  │ updated_at         │    │ updated_at                          │ │
│  └────────────────────┘    └─────────────────────────────────────┘ │
│                                                                     │
│  AFTER INSERT OR UPDATE → notify_catalog_update() trigger           │
│  → pg_notify('catalog_updates', JSON payload)                      │
└────────────────────────────┬────────────────────────────────────────┘
                             │  pg_notify over TCP
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GOOGLE COMPUTE ENGINE e2-micro VM                     │
│              Name: webserver  Zone: us-east4-b                     │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ Cloud SQL Auth Proxy (systemd: cloud-sql-proxy.service)      │  │
│  │ Listens: localhost:5432                                       │  │
│  │ Tunnels to Cloud SQL via VM service account identity         │  │
│  │ (IAM role: roles/cloudsql.client)                            │  │
│  └──────────────────┬──────────────────────────────────────────┘  │
│                     │                                              │
│  ┌──────────────────▼──────────────────────────────────────────┐  │
│  │ timeseries-listener (systemd: port 8080)                    │  │
│  │                                                              │  │
│  │ • LISTEN catalog_updates (persistent connection)            │  │
│  │ • select() non-blocking I/O wait (30s timeout)              │  │
│  │ • handle_update(): compute_hash() → site_state dict lookup  │  │
│  │ • Hash match → SKIP (no downstream action)                  │  │
│  │ • Hash miss → update site_state → POST to updater           │  │
│  │                                                              │  │
│  │ Flask API: GET / (health), GET /state, POST /flush          │  │
│  └──────────────────┬──────────────────────────────────────────┘  │
│                     │  POST /update (localhost:8081)              │
│  ┌──────────────────▼──────────────────────────────────────────┐  │
│  │ timeseries-updater (systemd: port 8081)                     │  │
│  │                                                              │  │
│  │ • Receives payload: {table, action, id, name, updated_at}   │  │
│  │ • datasets rows: SELECT full row from SQL                   │  │
│  │ • Reconstruct JSON entry from SQL row + metadata JSONB      │  │
│  │ • Patch data/models.json (update in place or append)        │  │
│  │ • git add data/models.json → git commit → git push          │  │
│  │ • models rows: skip (derived dynamically in browser JS)     │  │
│  │                                                              │  │
│  │ Flask API: GET / (health), POST /update, POST /rebuild      │  │
│  └──────────────────┬──────────────────────────────────────────┘  │
│                     │  git push (HTTPS + PAT)                     │
└─────────────────────┼───────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GITHUB REPOSITORY                                      │
│              UVA-MLSys/Time-Series-Commons                         │
│              Branch: server-functionality                           │
│                                                                     │
│  Auto-commit: "auto: updated entry 'Dataset Name' [UPDATE]"        │
│  Triggers GitHub Pages deployment pipeline                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │  ~1-3 min redeploy
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│              GITHUB PAGES                                           │
│              uva-mlsys.github.io/Time-Series-Commons               │
│                                                                     │
│  Browser fetch('./data/models.json') → NotebookCatalog class       │
│  → 790+ datasets rendered with domain filtering, search, modals    │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 Component Inventory

| Component | Technology | Host | Port | Managed by |
|---|---|---|---|---|
| Source database | PostgreSQL 18 | Google Cloud SQL | 5432 | Cloud SQL managed service |
| Auth tunnel | Cloud SQL Auth Proxy v2.14.1 | e2-micro VM | 5432 (localhost) | systemd |
| Catalog listener | Python 3.11 + psycopg2 + Flask | e2-micro VM | 8080 | systemd |
| Website updater | Python 3.11 + psycopg2 + Flask | e2-micro VM | 8081 | systemd |
| Artifact repository | Git | GitHub | — | GitHub Actions (Pages) |
| Website | HTML5 + Vanilla JS | GitHub Pages | 443 | GitHub |

---

## 4. Database Schema

### 4.1 Table: `datasets`

Stores metadata for every time series dataset discovered by DeepCollector or contributed by curators.

```sql
CREATE TABLE datasets (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,     -- canonical dataset name, deduplication key
    domain      TEXT,                     -- e.g. "Energy", "Transportation", "Health"
    source_url  TEXT,                     -- primary data access link
    metadata    JSONB,                    -- structured payload (see below)
    updated_at  TIMESTAMP DEFAULT NOW()
);
```

The `metadata` JSONB column stores the complete structured record, making the schema forward-compatible with DeepCollector additions without requiring migrations:

```json
{
  "slug":        "acsf1",
  "timePoints":  "1460",
  "interval":    "0.1Hz sampling, potentially resampled",
  "variables":   "1 (Univariate)",
  "dimensions":  "1",
  "description": "Power consumption signatures of 10 appliance categories...",
  "paperLink":   "https://doi.org/...",
  "benchmarks": {
    "Darts":       true,
    "Merlion":     true,
    "UCR":         false,
    "Timer-XL":    true,
    "Chronos-Pre": false
  }
}
```

The `benchmarks` sub-object captures which of the 78 benchmark evaluation frameworks have included this dataset, encoded as boolean flags. This directly mirrors the Y/X/blank notation in the source CSV spreadsheet.

### 4.2 Table: `models`

Stores metadata for each benchmark model or evaluation framework catalogued in the Commons.

```sql
CREATE TABLE models (
    id           SERIAL PRIMARY KEY,
    name         TEXT NOT NULL UNIQUE,    -- e.g. "Chronos-Eval1", "Timer-XL"
    architecture TEXT,                    -- e.g. "Transformer", "SSM", "LLM", "MLP"
    source_url   TEXT,                    -- GitHub repo, paper, or API portal
    metadata     JSONB,                   -- {description, datasetsCount}
    updated_at   TIMESTAMP DEFAULT NOW()
);
```

Architecture labels are assigned based on the model's design family:

| Architecture Label | Examples |
|---|---|
| Transformer | Informer, Chronos, Timer-XL, TimesFM, Lag-Llama |
| LLM | Time-LLM, AutoTimes, LLM-Time, One Fits All |
| SSM | TSMamba-ZS, TSMamba-FullShot, Time-MOE |
| MLP | TTM-PreT, TTM-Eval, Automixer |
| GNN | LightGTS |
| Contrastive | TS2Vec-Bench, TS2Vec-PreT |
| RAG | TS-RAGZSEval, TS-RAGPreT |
| Library/Benchmark | Darts, Merlion, Aeon, UCR, Monash, M1–M6 |

### 4.3 `UNIQUE` Constraints and Upsert Semantics

Both tables enforce `UNIQUE(name)`. This is required for the upsert pattern used by DeepCollector:

```sql
INSERT INTO datasets (name, domain, source_url, metadata)
VALUES (...)
ON CONFLICT (name) DO UPDATE
    SET domain     = EXCLUDED.domain,
        source_url = EXCLUDED.source_url,
        metadata   = EXCLUDED.metadata,
        updated_at = NOW();
```

The upsert pattern has two critical properties:
1. **Idempotency** — DeepCollector can be re-run on the same data without creating duplicate rows.
2. **Selective triggering** — PostgreSQL only fires the `AFTER UPDATE` trigger if the row actually changed, preventing spurious notifications for no-op updates.

---

## 5. The pub/sub Notification Mechanism

### 5.1 PostgreSQL `LISTEN`/`NOTIFY`

PostgreSQL's `pg_notify` function provides a lightweight asynchronous messaging channel built directly into the database. When a row is inserted or updated, a trigger function fires and publishes a JSON payload to a named channel. Any client holding a `LISTEN` connection on that channel receives the message asynchronously.

This is functionally equivalent to the MQTT broker role in the IndyCar system — a persistent, low-latency message bus that decouples the data writer (DeepCollector) from the data processor (the listener server).

### 5.2 Trigger Function

```sql
CREATE OR REPLACE FUNCTION notify_catalog_update()
RETURNS trigger AS $$
BEGIN
  PERFORM pg_notify(
    'catalog_updates',
    json_build_object(
      'table',      TG_TABLE_NAME,
      'action',     TG_OP,
      'id',         NEW.id,
      'name',       NEW.name,
      'updated_at', NEW.updated_at
    )::text
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER datasets_notify
AFTER INSERT OR UPDATE ON datasets
FOR EACH ROW EXECUTE FUNCTION notify_catalog_update();

CREATE TRIGGER models_notify
AFTER INSERT OR UPDATE ON models
FOR EACH ROW EXECUTE FUNCTION notify_catalog_update();
```

The payload is intentionally minimal — it carries only the routing information needed to identify the changed row, not the full row contents. The full row is fetched by the updater in a separate query, keeping the notify payload well within PostgreSQL's 8KB notification size limit and avoiding serialization of potentially large JSONB fields.

### 5.3 Example Notification Payload

```json
{
  "table":      "datasets",
  "action":     "INSERT",
  "id":         42,
  "name":       "M3 Competition",
  "updated_at": "2026-02-28T20:48:26.864000"
}
```

---

## 6. The Python Listener Server

### 6.1 Architecture

The listener (`timeseries-listener`, port 8080) runs as a persistent systemd service with `Restart=always`. It maintains two concurrent execution contexts:

1. **Listener thread** (daemon background thread): holds the PostgreSQL `LISTEN` connection and processes incoming notifications.
2. **Flask main thread**: serves the health and debug API.

### 6.2 The `select()` I/O Wait Pattern

The listener uses Python's `select.select()` for non-blocking I/O multiplexing on the database connection socket:

```python
ready = select.select([conn], [], [], 30)
if ready[0]:
    conn.poll()
    while conn.notifies:
        notify = conn.notifies.pop(0)
        handle_update(notify.payload)
```

This pattern, borrowed from Unix systems programming, avoids busy-polling. The thread sleeps for up to 30 seconds at a time, waking immediately when the socket becomes readable (i.e., when PostgreSQL delivers a notification). CPU utilization during idle periods is effectively zero, which is appropriate for the e2-micro's 1 shared vCPU constraint.

This is the direct analog of Apache Storm's spout polling pattern in the IndyCar system, where the MQTT subscriber thread blocks on the broker connection and wakes only when a message arrives.

### 6.3 The Hash Diff Gate

The hash diff gate is the central innovation of the system — the mechanism that prevents redundant downstream work, mirroring the HTM anomaly filter in the IndyCar architecture.

```python
site_state: dict[str, str] = {}   # "table:id" → md5(payload)

def compute_hash(payload: dict) -> str:
    return hashlib.md5(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()

def handle_update(payload_str: str) -> None:
    payload  = json.loads(payload_str)
    key      = f"{payload['table']}:{payload['id']}"
    new_hash = compute_hash(payload)

    if site_state.get(key) == new_hash:
        log.info(f"[SKIP] {key} — no change detected")
        return                              # absorb: no downstream action

    site_state[key] = new_hash             # record new state
    # ... POST to updater ...
```

`site_state` is an in-memory dictionary mapping row identifiers (`"datasets:42"`) to the MD5 hash of the last-seen notification payload. On each notification:

- If the hash matches the stored value, the payload is **absorbed** — the row's observable state has not changed, and no downstream work is initiated.
- If the hash differs (or the key is new), the state is updated and the payload is **propagated** to the website updater.

The hash is computed over the canonicalized JSON representation of the payload (`sort_keys=True` ensures deterministic ordering). Using MD5 for this purpose is appropriate: the hash is not used for cryptographic security, only for rapid equality comparison of small JSON payloads.

**Why this gate is necessary:** PostgreSQL fires `AFTER UPDATE` triggers even when an UPDATE statement does not change any values (e.g., `SET updated_at = updated_at`). The hash gate absorbs these no-op notifications without incurring a git commit and push, which would be wasteful on a resource-constrained VM.

### 6.4 Automatic Reconnection

The listener loop wraps the connection in a `while True` / `try-except` pattern with exponential sleep on `psycopg2.OperationalError`. If the Cloud SQL Auth Proxy restarts or the database connection is interrupted, the listener recovers automatically within 10 seconds without human intervention. This is a critical reliability property for a service running on a preemptible e2-micro instance.

### 6.5 Flask Health API

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Returns `{status: "running", tracked_rows: N}` |
| `/state` | GET | Returns the full `site_state` hash dictionary for debugging |
| `/flush` | POST | Clears `site_state`, forcing all next notifications to propagate regardless of hash match. Used after site redeploys. |

---

## 7. The Website Updater Service

### 7.1 Architecture

The updater (`timeseries-updater`, port 8081) receives the POST from the listener, queries Cloud SQL for the complete row, reconstructs the JSON entry, patches `data/models.json` in the local git clone, and pushes to GitHub.

### 7.2 Single-Row Patch (`POST /update`)

When a `datasets` row changes:

1. **Receive** the minimal payload from the listener: `{table, action, id, name, updated_at}`.
2. **Fetch** the full row from Cloud SQL: `SELECT id, name, domain, source_url, metadata FROM datasets WHERE id = $1`.
3. **Reconstruct** the JSON entry by inverting the seed mapping:

```python
def row_to_json_entry(row) -> dict:
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
```

4. **Load** `data/models.json`, find the matching entry by `name`, replace it in place (or append for new `INSERT` actions).
5. **Write** the patched JSON back to disk.
6. **Commit and push** via subprocess git calls.

This single-row patch is the core of the "react only to what changed" principle. A 540KB JSON file with 790 entries is parsed, one entry is updated, and the file is written back — rather than regenerating the entire catalog from scratch.

### 7.3 Full Rebuild (`POST /rebuild`)

The `/rebuild` endpoint provides a batch operation for initial seeding or recovery:

1. `SELECT * FROM datasets ORDER BY name` — fetch all rows.
2. Reconstruct the full `models[]` array.
3. Overwrite `data/models.json` completely.
4. Commit and push.

This is used once after seeding to establish the authoritative JSON state, and can be triggered manually at any time to resynchronize the file with the database after bulk imports.

### 7.4 Git Push Implementation

Git operations use `subprocess` to invoke the system git binary directly, with the GitHub PAT embedded in the remote URL for authentication:

```python
def git_push(commit_message: str) -> None:
    result = subprocess.run(
        ["git", "status", "--porcelain", "data/models.json"],
        cwd=REPO_LOCAL_PATH, capture_output=True, text=True
    )
    if not result.stdout.strip():
        return   # nothing to commit — idempotent

    subprocess.run(["git", "add", "data/models.json"],    ...)
    subprocess.run(["git", "commit", "-m", commit_message], ...)
    subprocess.run(["git", "push"],                         ...)
```

A thread lock (`threading.Lock`) serializes all git operations, preventing race conditions when multiple notifications arrive in rapid succession during a bulk import.

The `git status --porcelain` check before committing ensures idempotency: if the patch produced no change to the file content (e.g., a duplicate notification that arrived before the listener's hash gate could absorb it), no commit is created.

---

## 8. The Cloud SQL Auth Proxy

Direct TCP connections from the VM to Cloud SQL are routed through the Cloud SQL Auth Proxy (v2.14.1), which creates an encrypted mutual-TLS tunnel authenticated via the VM's Google service account identity (`430435578100-compute@developer.gserviceaccount.com`).

This eliminates the need to expose Cloud SQL on a public IP with password-only authentication, and removes the need to manage SSL certificates manually. The proxy runs as a systemd service that starts before both the listener and the updater (`After=cloud-sql-proxy.service`, `Requires=cloud-sql-proxy.service` in both unit files).

Connection architecture from the VM's perspective:

```
psycopg2.connect("host=127.0.0.1 port=5432 ...")
    ↓
Cloud SQL Auth Proxy (localhost:5432)
    ↓  mutual-TLS over TCP
Cloud SQL instance
project-4896a6b8-11ce-4f5a-ac4:us-east4:free-trial-first-project
```

---

## 9. End-to-End Latency

The total latency from a database write to a visible change on the public website has two components:

| Stage | Latency | Notes |
|---|---|---|
| SQL write → `pg_notify` | < 1ms | PostgreSQL trigger fires synchronously within the transaction |
| `pg_notify` → listener wakes | < 1ms | `select()` wakes immediately on socket readability |
| Hash diff check | < 1ms | In-memory dictionary lookup |
| Listener → updater POST | ~5ms | localhost HTTP |
| Updater SQL fetch | ~30ms | Round-trip to Cloud SQL via proxy |
| JSON patch + file write | ~50ms | Parsing 540KB + single entry update |
| Git commit + push | ~500ms | GitHub API round-trip |
| GitHub Pages redeploy | 60–180s | GitHub's build pipeline |
| **Total (DB write → site update)** | **~1–3 min** | Dominated by GitHub Pages |

For a research catalog updated by an agentic pipeline rather than a real-time trading system, this latency is appropriate. The pipeline can be upgraded to instant delivery in the future by replacing GitHub Pages with a VM-served API endpoint, reducing end-to-end latency to under 1 second.

---

## 10. Reliability and Fault Tolerance

### 10.1 systemd `Restart=always`

All three services (Cloud SQL Auth Proxy, listener, updater) run under systemd with `Restart=always` and `RestartSec=5`. A crash or OOM kill on the e2-micro's 1GB RAM is automatically recovered within 5 seconds without human intervention.

### 10.2 Service Dependency Ordering

```
cloud-sql-proxy.service
    ↑ required by
timeseries-listener.service
timeseries-updater.service
```

Both application services declare `Requires=cloud-sql-proxy.service` and `After=cloud-sql-proxy.service`, ensuring the auth tunnel is established before either service attempts a database connection.

### 10.3 Listener Auto-Reconnection

The `listener_loop()` function catches `psycopg2.OperationalError` and retries with a 10-second backoff, handling Cloud SQL proxy restarts, instance maintenance windows, and transient network interruptions.

### 10.4 Git Idempotency

The git push path checks `git status --porcelain` before committing. Combined with the listener's hash diff gate, duplicate notifications produce no git commits, preventing commit log pollution during bulk imports.

### 10.5 Updater Thread Lock

The `_git_lock = threading.Lock()` in the updater serializes all filesystem and git operations. Concurrent HTTP requests to `/update` (possible during bulk DeepCollector runs) queue behind the lock rather than racing on the JSON file.

---

## 11. Data Pipeline: From CSV to SQL to Website

The complete data lifecycle is:

```
1. Research discovery (manual or DeepCollector)
        ↓
2. Source CSV: Time-Series Common_Data_1-5-2026_COMBINED2.csv
        ↓  scripts/csv_to_json.py
3. data/models.json (815+ entries, 540KB)
        ↓  server/seed_data.py (one-time migration)
4. Cloud SQL timeseries_db.datasets (790 unique rows after deduplication)
        ↓  On any INSERT or UPDATE
5. pg_notify → listener → hash diff → updater
        ↓  Patch single entry
6. data/models.json (791+ entries)
        ↓  git push
7. GitHub repo commit
        ↓  GitHub Pages pipeline (~2 min)
8. uva-mlsys.github.io/Time-Series-Commons (public website)
        ↓  Browser fetch('./data/models.json')
9. NotebookCatalog class renders 790+ datasets
```

After the initial seeding, steps 1 and 4 are the only manual inputs. Steps 4 through 9 are fully automated and event-driven.

---

## 12. Security Considerations

| Concern | Mitigation |
|---|---|
| Cloud SQL network exposure | Auth Proxy only; no public IP required for VM connections |
| Database credentials | Stored in `~/.env` with `chmod 600`; never committed to git (`.gitignore`) |
| GitHub write access | PAT embedded in git remote URL on VM; not stored in repo |
| VM service account | Minimal `roles/cloudsql.client` scope; VM API scope `cloud-platform` |
| SQL injection | All queries use psycopg2 parameterized statements (`%s` placeholders) |
| JSONB injection | Metadata is stored as opaque JSONB; not interpolated into SQL strings |

---

## 13. Repository Structure

```
Time-Series-Commons/
├── data/
│   └── models.json                   # Generated artifact (source of truth: SQL)
├── js/
│   └── models.js                     # NotebookCatalog class, fetches models.json
├── server/
│   ├── schema.sql                    # DDL: tables, triggers, notify function
│   ├── seed_data.py                  # One-time migration: models.json → SQL
│   ├── listener/
│   │   ├── main.py                   # LISTEN/NOTIFY server + hash diff gate
│   │   ├── requirements.txt
│   │   └── .env.example
│   ├── updater/
│   │   ├── main.py                   # Website updater: SQL → JSON → git push
│   │   ├── requirements.txt
│   │   └── .env.example
│   └── systemd/
│       ├── cloud-sql-proxy.service
│       ├── timeseries-listener.service
│       └── timeseries-updater.service
├── scripts/
│   └── csv_to_json.py                # CSV → models.json converter
├── .gitignore                        # Excludes .env files
└── ARCHITECTURE.md                   # This document
```

---

## 14. Future Extensions

The current architecture provides a clean foundation for several extensions:

1. **Sub-second site updates**: Replace GitHub Pages with a VM-hosted Express/FastAPI server that serves `data/models.json` directly. The updater writes to the in-memory data layer rather than a file, eliminating the GitHub Pages redeploy latency entirely.

2. **DeepCollector integration**: The DeepCollector LLM pipeline connects to Cloud SQL via the public IP with `sslmode=require` and uses the same upsert pattern (`ON CONFLICT (name) DO UPDATE`). No changes to the listener or updater are required — any write from any source triggers the pipeline automatically.

3. **Deletion handling**: The current trigger only fires on `INSERT` and `UPDATE`. A `BEFORE DELETE` trigger with a soft-delete `is_active` column would allow catalog entries to be unpublished from the website without being destroyed in the database.

4. **Audit log**: A separate `catalog_events` table populated by the trigger function would provide a complete history of all changes for research reproducibility and provenance tracking.

5. **MLCommons Croissant metadata**: The `metadata` JSONB column is already designed to be forward-compatible with the MLCommons Croissant metadata standard. Fields not yet mapped can be added by DeepCollector without schema migrations.

---

*Document maintained by the UVA Machine Learning Systems Research Group.*  
*Last updated: February 2026.*
