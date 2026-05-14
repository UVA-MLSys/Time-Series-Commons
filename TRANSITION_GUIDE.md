# Time Series Commons — Project Transition Guide

This document is the complete handoff reference for the **Time Series Commons** project.
It covers everything a new maintainer needs: architecture, server access, credentials, daily operations, and troubleshooting.

---

## Table of Contents

1. [What This Project Is](#1-what-this-project-is)
2. [Architecture Overview](#2-architecture-overview)
3. [Getting Access](#3-getting-access)
4. [Credentials — First Thing to Change](#4-credentials--first-thing-to-change)
5. [The Server — File Layout](#5-the-server--file-layout)
6. [Managing the Services](#6-managing-the-services)
7. [Deploying a Code Change](#7-deploying-a-code-change)
8. [The Database (Cloud SQL / PostgreSQL)](#8-the-database-cloud-sql--postgresql)
9. [Adding or Updating a Dataset](#9-adding-or-updating-a-dataset)
10. [The AI Assistant](#10-the-ai-assistant)
11. [Google Cloud Console](#11-google-cloud-console)
12. [GitHub & the Static Site](#12-github--the-static-site)
13. [Testing the Full Pipeline](#13-testing-the-full-pipeline)
14. [Troubleshooting](#14-troubleshooting)
15. [Quick Reference Cheatsheet](#15-quick-reference-cheatsheet)

---

## 1. What This Project Is

**Time Series Commons** is an open catalog of time-series datasets and models, published as a static website on GitHub Pages at the **UVA-MLSys/Time-Series-Commons** repository.

The site itself is plain HTML/CSS/JavaScript with no build step. The catalog data lives in `data/models.json`, which is automatically kept in sync with a PostgreSQL database running on Google Cloud SQL.

### How data gets onto the site

```
Producer (script / DeepCollector)
    │
    │  POST /ingest  (with Bearer token)
    ▼
Broker (FastAPI, port 8083)
    │  validates auth, enriches domain, writes to Cloud SQL
    │  pg_notify fires on INSERT/UPDATE/DELETE
    ▼
Listener (Flask, port 8080)
    │  receives NOTIFY, MD5-diffs to skip duplicates
    │  POSTs to Updater
    ▼
Updater (Flask, port 8081)
    │  fetches full row from SQL
    │  patches data/models.json
    │  git commit + git push
    ▼
GitHub Pages redeploys (~1–3 min lag)
    │
    ▼
Live website updated
```

---

## 2. Architecture Overview

| Component | Tech | Where it runs | Port |
|-----------|------|---------------|------|
| Static website | HTML/CSS/JS | GitHub Pages | — |
| Catalog Broker | FastAPI + Python 3.11 | GCP VM (Debian 12) | 8083 |
| Catalog Listener | Flask + psycopg2 | GCP VM | 8080 |
| Website Updater | Flask + psycopg2 + git | GCP VM | 8081 |
| AI Assistant | Flask + Google Gemini | GCP VM | 8082 |
| Database | PostgreSQL 14 | Google Cloud SQL | 5432 (local only via proxy) |
| DB Tunnel | Cloud SQL Auth Proxy v2 | GCP VM (system) | 5432 → Cloud SQL |

### Key files on the VM

```
~/credentials.env            ← SINGLE SOURCE OF TRUTH for all credentials
~/apply-credentials.sh       ← Run after editing credentials.env
~/Time-Series-Commons/       ← Git repo clone (also used as git working tree by updater)
~/timeseries-broker/         ← Broker service working dir (main.py is a symlink → repo)
~/timeseries-listener/       ← Listener service working dir (symlink)
~/timeseries-updater/        ← Updater service working dir (symlink)
~/timeseries-ai/             ← AI service working dir (symlink)
~/service-backups-*/         ← Timestamped backups of original .py files before symlinks
```

All `.py` files in the service dirs are **symlinks** into the repo clone.
A `git pull` in `~/Time-Series-Commons/` immediately updates what all services run.

---

## 3. Getting Access

### SSH into the server

**Server IP:** `35.221.32.85` (GCP us-east4, Debian GNU/Linux 12)
**Login user:** `ryangoudjil`

```bash
ssh ryangoudjil@35.221.32.85
```

Your SSH public key must be in `~/.ssh/authorized_keys` on the server. To add it:

1. On your local machine, run:
   ```bash
   cat ~/.ssh/id_ed25519.pub
   # or if you use RSA:
   cat ~/.ssh/id_rsa.pub
   ```
2. Copy the full output line
3. On the server (ask the previous owner to run):
   ```bash
   echo "ssh-ed25519 AAAA...your-key... you@yourmachine" >> ~/.ssh/authorized_keys
   ```

### GCP Console access

- **Project ID:** `project-4896a6b8-11ce-4f5a-ac4`
- **Region:** `us-east4`

Ask the previous owner to add your Google account as an **Owner** or **Editor** in:
GCP Console → IAM & Admin → IAM → Grant Access

### GitHub access

Repository: `https://github.com/UVA-MLSys/Time-Series-Commons`

Ask the previous owner to add you as a **Maintainer** on the UVA-MLSys GitHub organization, or transfer the repo to your own org.

---

## 4. Credentials — First Thing to Change

All credentials live in **one file** on the server:

```bash
nano ~/credentials.env
```

### What you MUST change when taking over

| Variable | What it is | How to get a new one |
|----------|-----------|----------------------|
| `GITHUB_PAT` | GitHub Personal Access Token used to push to the repo | github.com → Settings → Developer settings → Personal access tokens → Fine-grained → Contents: Read & Write on the repo |
| `GITHUB_USERNAME` | GitHub username that owns the PAT above | Your GitHub username |
| `GIT_AUTHOR_EMAIL` | Email on every automated git commit | Any email — your university email or a shared bot address |
| `GEMINI_API_KEY` | Google AI Studio key powering the AI assistant | aistudio.google.com/app/apikey (free tier available) |

### After editing, apply all changes at once

```bash
~/apply-credentials.sh
```

This rewrites all 4 service `.env` files, updates the git remote URL with the new PAT, and restarts all services. You do not need to touch any other file.

### Credentials you do NOT need to change immediately

| Variable | What it is | Notes |
|----------|-----------|-------|
| `DB_CONN_STR` | PostgreSQL connection string | Project credential, not personal |
| `BROKER_SECRET` | Bearer token for POST /ingest | Rotate only if compromised; update DeepCollector too |
| `WEBHOOK_SECRET` | Bearer token for Apps Script path | Only matters if using Google Sheets ingestion |

---

## 5. The Server — File Layout

```
/home/ryangoudjil/
├── credentials.env              # All credentials (chmod 600, NEVER commit to git)
├── apply-credentials.sh         # Propagates credentials to services + restarts them
├── service-backups-20260514/    # Backup of original .py files before symlink setup
│
├── Time-Series-Commons/         # Git repo clone
│   ├── data/
│   │   ├── models.json          # Live catalog — written by updater on every DB change
│   │   └── domain-config.json   # Domain keyword → canonical domain mapping
│   ├── server/
│   │   ├── broker/main.py       # Broker source (symlinked from timeseries-broker/)
│   │   ├── listener/main.py     # Listener source (symlinked)
│   │   ├── updater/main.py      # Updater source (symlinked)
│   │   ├── ai/main.py           # AI source (symlinked)
│   │   └── schema.sql           # PostgreSQL DDL (reference; DB already running)
│   └── [static site files]      # index.html, models.html, ai.html, css/, js/, pics/
│
├── timeseries-broker/
│   ├── main.py -> ../Time-Series-Commons/server/broker/main.py   (symlink)
│   ├── domain_resolver.py -> ../Time-Series-Commons/server/broker/domain_resolver.py
│   ├── venv/                    # Python virtualenv
│   └── .env                     # Written by apply-credentials.sh — do not edit directly
│
├── timeseries-listener/
│   ├── main.py -> ../Time-Series-Commons/server/listener/main.py
│   ├── venv/
│   └── .env
│
├── timeseries-updater/
│   ├── main.py -> ../Time-Series-Commons/server/updater/main.py
│   ├── venv/
│   └── .env
│
└── timeseries-ai/
    ├── main.py -> ../Time-Series-Commons/server/ai/main.py
    ├── venv/
    └── .env
```

---

## 6. Managing the Services

All 5 services are managed by **systemd** and start automatically on server boot.

### Check status of everything

```bash
systemctl status timeseries-broker timeseries-listener timeseries-updater timeseries-ai cloud-sql-proxy
```

### Restart a single service

```bash
sudo systemctl restart timeseries-broker    # swap in: listener / updater / ai
```

### Restart all services at once

```bash
sudo systemctl restart timeseries-broker timeseries-listener timeseries-updater timeseries-ai
```

### View live logs (streaming)

```bash
sudo journalctl -u timeseries-broker -f
sudo journalctl -u timeseries-updater -f     # most useful — shows git push results
sudo journalctl -u timeseries-ai -f
```

### View recent logs (last 50 lines, no pager)

```bash
sudo journalctl -u timeseries-updater -n 50 --no-pager
```

### Port map

| Service | Port | Exposed to | Notes |
|---------|------|------------|-------|
| Broker | 8083 | Internet | Requires `Authorization: Bearer <BROKER_SECRET>` |
| Listener | 8080 | Internet | Internal use only — should ideally be firewalled |
| Updater | 8081 | Internet | Internal use only — should ideally be firewalled |
| AI | 8082 | Internet | Accessed via sslip.io hostname from ai.html |
| Cloud SQL Proxy | 5432 | 127.0.0.1 only | Never exposed externally |

---

## 7. Deploying a Code Change

Because all `.py` files in the service directories are **symlinks** into the git repo clone, deploying is just pull + restart:

```bash
# SSH into the server
ssh ryangoudjil@35.221.32.85

# Pull latest code
cd ~/Time-Series-Commons
git pull

# Restart whichever service(s) changed
sudo systemctl restart timeseries-broker      # changed server/broker/main.py
sudo systemctl restart timeseries-updater     # changed server/updater/main.py
sudo systemctl restart timeseries-listener    # changed server/listener/main.py
sudo systemctl restart timeseries-ai          # changed server/ai/main.py
```

### If you change domain-config.json

The broker loads `domain-config.json` at startup. Restart it:

```bash
sudo systemctl restart timeseries-broker
```

### If you add a new Python dependency

```bash
source ~/timeseries-broker/venv/bin/activate     # activate the right venv
pip install <package>
deactivate
sudo systemctl restart timeseries-broker
```

---

## 8. The Database (Cloud SQL / PostgreSQL)

### Connection details

| Field | Value |
|-------|-------|
| GCP Instance | `project-4896a6b8-11ce-4f5a-ac4:us-east4:timeseries-db` |
| Database name | `timeseries_db` |
| User | `ts-user` |
| Password | See `DB_CONN_STR` in `~/credentials.env` (the `%40` is URL-encoded `@`) |
| Host (on VM) | `127.0.0.1:5432` via Cloud SQL Auth Proxy |

The Cloud SQL Auth Proxy (`cloud-sql-proxy.service`) runs as a systemd service and tunnels the connection to `127.0.0.1:5432`. You never connect directly to Cloud SQL's external IP — the proxy handles authentication via GCP IAM.

### Connect interactively on the server

```bash
psql "$(grep DB_CONN_STR ~/credentials.env | cut -d= -f2)"
```

Useful psql commands:

```sql
\dt                                              -- list tables
\d datasets                                      -- describe datasets table
SELECT count(*) FROM datasets;
SELECT name, domain, domain_canonical FROM datasets ORDER BY name LIMIT 10;
SELECT name FROM datasets WHERE name ILIKE '%climate%';
\q                                               -- quit
```

### Schema overview

**`datasets`** — one row per catalog entry
Key columns: `id`, `name`, `domain`, `domain_canonical`, `domain_image`, `source_url`, `metadata` (JSONB), `updated_at`

**`models`** — model entries (rarely written directly; mostly derived in JS from benchmark data in datasets.metadata)

PostgreSQL triggers on both tables fire `pg_notify` on three channels:
- `catalog_updates` — legacy generic channel
- `catalog_datasets` — dataset-specific
- `catalog_models` — model-specific

The Listener subscribes to all three and wakes up whenever any row changes.

### Rotating the DB password

1. GCP Console → SQL → `timeseries-db` → Users → edit `ts-user`
2. Set new password; URL-encode any `@` as `%40`
3. Edit `~/credentials.env` and update `DB_CONN_STR`
4. Run `~/apply-credentials.sh`

---

## 9. Adding or Updating a Dataset

### Via the REST API (recommended for single entries)

Replace `<BROKER_SECRET>` with the value from `~/credentials.env`.

```bash
curl -X POST http://35.221.32.85:8083/ingest \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <BROKER_SECRET>' \
  -d '{
    "table": "datasets",
    "action": "UPSERT",
    "record": {
      "name": "My Dataset Name",
      "domain": "Climate",
      "source_url": "https://example.com/dataset",
      "metadata": {
        "slug": "my-dataset-name",
        "timePoints": "10000",
        "interval": "Hourly",
        "variables": "5",
        "dimensions": "1",
        "description": "A description of the dataset.",
        "paperLink": "https://arxiv.org/abs/..."
      }
    }
  }'
```

`action` can be `"UPSERT"` (default) or `"DELETE"`. The broker automatically resolves the `domain` field to a canonical domain and image using `data/domain-config.json`.

### Batch ingest

```bash
curl -X POST http://35.221.32.85:8083/ingest/batch \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <BROKER_SECRET>' \
  -d '{
    "records": [
      {"table": "datasets", "action": "UPSERT", "record": {"name": "Dataset A", ...}},
      {"table": "datasets", "action": "UPSERT", "record": {"name": "Dataset B", ...}}
    ]
  }'
```

### Force a full rebuild of models.json

Useful after bulk DB changes or if the JSON gets out of sync:

```bash
# Run on the server
curl -X POST http://127.0.0.1:8081/rebuild
# Watch logs:
sudo journalctl -u timeseries-updater -f
```

### Bulk CSV import

```bash
cd ~/Time-Series-Commons
source ~/seed-venv/bin/activate
DB_CONN_STR="$(grep DB_CONN_STR ~/credentials.env | cut -d= -f2)" \
  python3 scripts/update_links_from_csv.py
```

---

## 10. The AI Assistant

- **Service:** `timeseries-ai` — Flask on port 8082
- **Model:** Gemini flash (see `server/ai/main.py` for exact model string)
- **How it works:** At startup the service reads `data/models.json` and embeds the full catalog (≈125K tokens) in every Gemini system prompt. Gemini's implicit caching means repeated prefixes are cached server-side at no extra cost.
- **Public URL:** Hardcoded in `ai.html` as `AI_SERVER_URL`. Currently points to the sslip.io hostname for this server's IP.

### Restart to pick up catalog changes

```bash
sudo systemctl restart timeseries-ai
```

### Update AI_SERVER_URL if the server IP changes

```bash
# On your local machine in the repo:
# Edit ai.html and update the AI_SERVER_URL constant
git add ai.html
git commit -m "update AI_SERVER_URL to new IP"
git push
```

Long-term: set up a real domain name so this never needs to change.

---

## 11. Google Cloud Console

Login: `https://console.cloud.google.com`
Project: `project-4896a6b8-11ce-4f5a-ac4`

### Tasks and where to find them

| Task | Console path |
|------|-------------|
| View / SSH / restart the VM | Compute Engine → VM Instances → `webserver` |
| Change DB password | SQL → `timeseries-db` → Users |
| View active DB connections | SQL → `timeseries-db` → Connections |
| View/edit firewall rules | VPC network → Firewall |
| Check billing | Billing |
| View Cloud SQL logs | Logging → resource: Cloud SQL Database |
| SSH via browser (no key needed) | Compute Engine → VM → SSH button |
| Transfer project ownership | IAM & Admin → IAM → Grant Access |

### If the VM stops or reboots

All 5 services are `enabled` in systemd — they restart automatically on boot.
If something does not come back:

```bash
sudo systemctl start cloud-sql-proxy         # start DB tunnel first
sleep 5
sudo systemctl start timeseries-broker timeseries-listener timeseries-updater timeseries-ai
sudo systemctl status timeseries-broker timeseries-listener timeseries-updater timeseries-ai cloud-sql-proxy
```

---

## 12. GitHub & the Static Site

**Repository:** `https://github.com/UVA-MLSys/Time-Series-Commons`
**Published branch (GitHub Pages):** `main`
**Server working branch:** `feature/pubsub-broker`

The updater pushes automated `data/models.json` commits to `feature/pubsub-broker`. To get those onto the live site, merge into `main`:

```bash
cd ~/Time-Series-Commons
git checkout main
git pull origin main
git merge feature/pubsub-broker
git push origin main
git checkout feature/pubsub-broker     # switch back so the updater keeps working
```

Or open a PR on GitHub from `feature/pubsub-broker` → `main`.

### Creating a new GitHub PAT for the server

1. `github.com` → Settings → Developer settings → Personal access tokens → Fine-grained tokens
2. Click **Generate new token**
3. Repository access: `UVA-MLSys/Time-Series-Commons` only
4. Permissions: **Contents → Read and write**
5. Copy the token
6. On the server:
   ```bash
   nano ~/credentials.env      # update GITHUB_USERNAME and GITHUB_PAT
   ~/apply-credentials.sh      # applies to git remote + restarts services
   ```
7. Revoke the old PAT from the previous owner's GitHub account settings

---

## 13. Testing the Full Pipeline

Run this to verify the entire chain is working — from API to git push:

```bash
# From your local machine (replace <BROKER_SECRET> with value from credentials.env)

# Step 1: Health check
curl http://35.221.32.85:8083/health

# Step 2: Insert a test entry
curl -X POST http://35.221.32.85:8083/ingest \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <BROKER_SECRET>' \
  -d '{
    "table": "datasets",
    "action": "UPSERT",
    "record": {
      "name": "__TEST_DATASET__",
      "domain": "Climate",
      "source_url": "https://example.com/test",
      "metadata": {"slug": "test-dataset", "description": "Pipeline health check"}
    }
  }'

# Step 3: On the server, watch the updater push to GitHub:
sudo journalctl -u timeseries-updater -f
# Expected: [GIT] Pushed: auto: appended new entry '__TEST_DATASET__' [INSERT]

# Step 4: Clean up
curl -X POST http://35.221.32.85:8083/ingest \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer <BROKER_SECRET>' \
  -d '{"table":"datasets","action":"DELETE","record":{"name":"__TEST_DATASET__"}}'
```

---

## 14. Troubleshooting

### A service is down

```bash
sudo systemctl status timeseries-broker
sudo journalctl -u timeseries-broker -n 50 --no-pager    # read the error
sudo systemctl restart timeseries-broker
```

### git push fails (updater log shows non-zero exit status 1)

The remote branch has commits the server does not have:

```bash
cd ~/Time-Series-Commons
git pull --no-rebase origin feature/pubsub-broker
git push origin feature/pubsub-broker
```

### git push fails (authentication error / 403)

The GitHub PAT has expired or been revoked:

```bash
nano ~/credentials.env      # update GITHUB_PAT
~/apply-credentials.sh
```

### Cloud SQL proxy is down (DB connection refused)

```bash
sudo systemctl status cloud-sql-proxy
sudo systemctl restart cloud-sql-proxy
sleep 5
sudo systemctl restart timeseries-broker timeseries-listener timeseries-updater
```

### models.json is stale or corrupted

```bash
curl -X POST http://127.0.0.1:8081/rebuild
sudo journalctl -u timeseries-updater -f    # wait for "Pushed: auto: full rebuild"
```

### AI returns errors or stale catalog data

```bash
sudo systemctl restart timeseries-ai        # reloads models.json at startup
```

### Roll back a service to its pre-symlink code

```bash
rm ~/timeseries-updater/main.py
cp ~/service-backups-20260514-200756/timeseries-updater/main.py ~/timeseries-updater/main.py
sudo systemctl restart timeseries-updater
# To re-enable symlinks later:
# rm ~/timeseries-updater/main.py
# ln -s ~/Time-Series-Commons/server/updater/main.py ~/timeseries-updater/main.py
```

---

## 15. Quick Reference Cheatsheet

```bash
# ── ACCESS ────────────────────────────────────────────────────────────────────
ssh ryangoudjil@35.221.32.85

# ── CREDENTIALS ───────────────────────────────────────────────────────────────
nano ~/credentials.env
~/apply-credentials.sh                          # apply + restart all services

# ── SERVICE MANAGEMENT ────────────────────────────────────────────────────────
systemctl status timeseries-{broker,listener,updater,ai} cloud-sql-proxy
sudo systemctl restart timeseries-broker timeseries-listener timeseries-updater timeseries-ai
sudo journalctl -u timeseries-updater -f        # live log stream

# ── DEPLOYING CODE ────────────────────────────────────────────────────────────
cd ~/Time-Series-Commons && git pull
sudo systemctl restart timeseries-<service>     # whichever file changed

# ── DATABASE ──────────────────────────────────────────────────────────────────
psql "$(grep DB_CONN_STR ~/credentials.env | cut -d= -f2)"

# ── CATALOG OPERATIONS ────────────────────────────────────────────────────────
curl http://35.221.32.85:8083/health            # health check
curl -X POST http://127.0.0.1:8081/rebuild      # rebuild models.json from DB

# Ingest a dataset:
curl -X POST http://35.221.32.85:8083/ingest \
  -H 'Authorization: Bearer <BROKER_SECRET>' \
  -H 'Content-Type: application/json' \
  -d '{"table":"datasets","action":"UPSERT","record":{"name":"...","domain":"...","metadata":{}}}'
```

---

*Last updated: May 2026 · UVA MLSys Group · Repository: github.com/UVA-MLSys/Time-Series-Commons*
