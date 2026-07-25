# Time Series Commons — Catalog Broker

The **Catalog Broker** is the new ingestion entry point for the Time Series
Commons pipeline. It replaces the Google Sheets → Apps Script → `/ingest-from-sheets`
path with a direct, authenticated JSON API that DeepCollector (or any producer)
can call.

---

## Architecture

```
DeepCollector
    │
    │  POST /ingest  (Bearer token)
    ▼
┌──────────────────────────────────────┐
│  Catalog Broker  :8083               │
│  server/broker/main.py               │
│                                      │
│  1. Authenticate (BROKER_SECRET)     │
│  2. Resolve domain → canonical +     │
│     image  (DomainResolver)          │
│  3. UPSERT / DELETE → PostgreSQL     │
└──────────────────────────────────────┘
    │
    │  pg_notify  →  catalog_updates
    │              + catalog_datasets  (or catalog_models)
    ▼
┌──────────────────────────────────────┐
│  Catalog Listener  :8080             │
│  server/listener/main.py             │
│  (subscribes to all three channels)  │
└──────────────────────────────────────┘
    │
    │  POST /update
    ▼
┌──────────────────────────────────────┐
│  Website Updater  :8081              │
│  server/updater/main.py              │
│  → patches data/models.json          │
│  → git push → GitHub Pages           │
└──────────────────────────────────────┘
```

### IndyCar-master analogy

| IndyCar component              | Time Series Commons equivalent          |
|-------------------------------|----------------------------------------|
| Race log / TCP stream          | DeepCollector discovery output          |
| Events Publisher               | **This broker service**                |
| MQTT Pub/Sub Broker (Apollo)   | PostgreSQL LISTEN/NOTIFY               |
| Per-car MQTT topics            | `catalog_datasets`, `catalog_models`   |
| Storm Cluster                  | Catalog Listener (hash-diff gate)      |
| MongoDB                        | PostgreSQL                             |

---

## Domain + Image Auto-Assignment

Every record ingested through the broker is automatically enriched with:

- **`domain_canonical`** — one of the 15 canonical domain names (e.g. `"Energy"`)
- **`domain_image`** — relative image path (e.g. `"pics/domains/energy.jpg"`)

The resolver (`domain_resolver.py`) reads `data/domain-config.json` and matches
the raw `domain` field against keyword lists using this priority:

1. Exact case-insensitive match on canonical name (`"energy"` → `"Energy"`)
2. Longest-keyword-first substring match (`"Device (Energy Consumption)"` → `"Energy"`)
3. Fallback → `"Synthetic"` for unknown or empty domains

DeepCollector only needs to supply the raw domain string — no manual tagging needed.

---

## Setup

### 1. Create the virtualenv

```bash
mkdir -p ~/timeseries-broker && cd ~/timeseries-broker
python3 -m venv venv
source venv/bin/activate
pip install -r /path/to/repo/server/broker/requirements.txt
```

### 2. Copy service files

```bash
cp /path/to/repo/server/broker/main.py            ~/timeseries-broker/main.py
cp /path/to/repo/server/broker/domain_resolver.py ~/timeseries-broker/domain_resolver.py
```

### 3. Configure environment

```bash
cp /path/to/repo/server/broker/.env.example ~/timeseries-broker/.env
chmod 600 ~/timeseries-broker/.env
# Edit and fill in:
#   DB_CONN_STR          — PostgreSQL connection string
#   BROKER_SECRET        — strong random secret (see .env.example)
#   DOMAIN_CONFIG_PATH   — absolute path to data/domain-config.json
```

### 4. Apply the schema migration

The updated `schema.sql` adds `domain_canonical` and `domain_image` columns
and the DELETE trigger. Apply it once against your existing database:

```bash
psql "$DB_CONN_STR" -f /path/to/repo/server/schema.sql
```

The `ALTER TABLE … ADD COLUMN IF NOT EXISTS` statements are idempotent.

### 5. Open firewall port 8083

Allow inbound traffic from DeepCollector's IP only:

```bash
gcloud compute firewall-rules create allow-broker \
  --allow tcp:8083 \
  --source-ranges=<DEEPCOLLECTOR_IP>/32 \
  --description="Catalog Broker ingestion endpoint"
```

### 6. Enable the systemd service

```bash
sudo cp /path/to/repo/server/systemd/timeseries-broker.service \
        /etc/systemd/system/timeseries-broker.service
sudo systemctl daemon-reload
sudo systemctl enable timeseries-broker
sudo systemctl start timeseries-broker
sudo systemctl status timeseries-broker
```

---

## API Reference

### `GET /health`

Liveness check. Returns the list of active canonical domains.

```json
{
  "status": "running",
  "port": 8083,
  "canonical_domains": ["Energy", "Synthetic", "Image", ...]
}
```

---

### `POST /ingest`

Upsert or delete a single dataset or model.

**Auth:** `Authorization: Bearer <BROKER_SECRET>`

**Body:**

```json
{
  "table":  "datasets",
  "action": "UPSERT",
  "record": {
    "name":       "M3 Competition",
    "domain":     "Economics",
    "source_url": "https://forecasting-benchmark.com/m3",
    "metadata": {
      "slug":        "m3-competition",
      "timePoints":  "3003",
      "interval":    "Monthly",
      "variables":   "1",
      "dimensions":  "1",
      "description": "Classic M3 forecasting competition dataset.",
      "paperLink":   "https://doi.org/10.1016/S0169-2070(00)00057-1",
      "benchmarks":  { "Darts": true, "Merlion": false }
    }
  }
}
```

**Response (200):**

```json
{
  "name":             "M3 Competition",
  "table":            "datasets",
  "action":           "UPSERT",
  "status":           "inserted",
  "domain_canonical": "Economics",
  "domain_image":     "pics/domains/economics.jpg"
}
```

---

### `POST /ingest/batch`

Bulk upsert / delete — processes all records in a single transaction.

**Body:**

```json
{
  "records": [
    { "table": "datasets", "action": "UPSERT", "record": { ... } },
    { "table": "datasets", "action": "DELETE", "record": { "name": "OldDataset" } }
  ]
}
```

**Response (200):**

```json
{
  "status":   "ok",
  "total":    2,
  "inserted": 1,
  "updated":  0,
  "deleted":  1,
  "results":  [ ... ]
}
```

---

## DeepCollector Integration

Point DeepCollector at the broker instead of Google Sheets:

```python
import requests

BROKER_URL    = "http://<VM_IP>:8083"
BROKER_SECRET = "<your secret>"

def publish_dataset(record: dict):
    resp = requests.post(
        f"{BROKER_URL}/ingest",
        json={"table": "datasets", "action": "UPSERT", "record": record},
        headers={"Authorization": f"Bearer {BROKER_SECRET}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()

def publish_batch(records: list[dict]):
    payload = [
        {"table": "datasets", "action": "UPSERT", "record": r}
        for r in records
    ]
    resp = requests.post(
        f"{BROKER_URL}/ingest/batch",
        json={"records": payload},
        headers={"Authorization": f"Bearer {BROKER_SECRET}"},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()
```

---

## Legacy Path (Google Sheets)

The `server/sheets-sync/` Apps Script and the `/ingest-from-sheets` endpoint
on the updater remain functional as a fallback. The broker is the preferred
path for all new writes; the Sheets sync can be retired once DeepCollector is
fully pointed at the broker.
