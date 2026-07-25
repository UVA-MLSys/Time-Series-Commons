"""
Broker test suite — two modes:

  Mode 1  (no DB needed, runs anywhere):
      python test_broker.py

  Mode 2  (full integration, needs proxy tunnel at 127.0.0.1:5432):
      LIVE_DB=1 DB_CONN_STR="postgresql://..." python test_broker.py

Tests:
  - DomainResolver — all 15 canonical domains + fallback
  - FastAPI endpoints with mocked DB (mode 1) or real DB (mode 2)
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# ── path so imports work from any cwd ────────────────────────────────────────
BROKER_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.join(BROKER_DIR, "..", "..")
sys.path.insert(0, BROKER_DIR)

DOMAIN_CONFIG_PATH = os.path.join(REPO_ROOT, "data", "domain-config.json")

# ─────────────────────────────────────────────────────────────────────────────
# Helper — colour output
# ─────────────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

passed = failed = 0


def ok(label):
    global passed
    passed += 1
    print(f"  {GREEN}✓{RESET}  {label}")


def fail(label, detail=""):
    global failed
    failed += 1
    print(f"  {RED}✗  {label}{RESET}")
    if detail:
        print(f"     {RED}{detail}{RESET}")


def section(title):
    print(f"\n{BOLD}{title}{RESET}")
    print("─" * 60)


# ═════════════════════════════════════════════════════════════════════════════
# 1. DomainResolver tests (no DB, no network)
# ═════════════════════════════════════════════════════════════════════════════

section("1 · DomainResolver — keyword matching")

from domain_resolver import DomainResolver

try:
    r = DomainResolver(DOMAIN_CONFIG_PATH)
    ok("Loaded domain-config.json successfully")
except Exception as e:
    fail("Load domain-config.json", str(e))
    print(f"\n{RED}Cannot continue without domain config.{RESET}")
    sys.exit(1)

cases = [
    # (input,                              expected_canonical)
    ("Device (Energy Consumption)",        "Energy"),
    ("ECG",                                "Health"),
    ("Air Quality",                        "Nature"),
    ("Financial",                          "Economics"),
    ("HAR",                                "Motion"),
    ("Human Activity Recognition",         "Motion"),
    ("Transportation",                     "Transportation"),
    ("Computer Vision",                    "Image"),
    ("Industrial IoT",                     "Industry"),
    ("manufacturing predictive maintenance","Industry"),
    ("Retail Sales Forecasting",           "Retail"),
    ("Speech Recognition",                 "Audio"),
    ("Demographics",                       "Demographics"),
    ("Sensor Network",                     "Sensor"),
    ("Energy",                             "Energy"),      # exact canonical match
    ("energy",                             "Energy"),      # case-insensitive
    ("",                                   "Synthetic"),   # empty → fallback
    ("completely unknown xyz 12345",       "Synthetic"),   # no match → fallback
]

for domain_text, expected in cases:
    result = r.resolve(domain_text)
    if result["canonical"] == expected:
        ok(f'"{domain_text}"  →  {result["canonical"]}  ({result["image"]})')
    else:
        fail(
            f'"{domain_text}"  →  expected {expected}, got {result["canonical"]}',
        )

section("1b · DomainResolver — all canonical domains covered")
names = r.canonical_names()
# domain-config.json has 14 domains (Microeconomics merged into Economics)
expected_count = len(json.load(open(DOMAIN_CONFIG_PATH))["domains"])
if len(names) == expected_count:
    ok(f"{expected_count} canonical domains loaded: {', '.join(names)}")
else:
    fail(f"Expected {expected_count} domains, got {len(names)}: {names}")

for name in names:
    res = r.resolve(name)
    if res["canonical"] == name and res["image"]:
        ok(f"{name}  →  {res['image']}")
    else:
        fail(f"{name} self-resolve failed", str(res))


# ═════════════════════════════════════════════════════════════════════════════
# 2. FastAPI endpoint tests (mocked DB)
# ═════════════════════════════════════════════════════════════════════════════

section("2 · FastAPI endpoints (mocked DB)")

# Set required env vars before importing main
os.environ.setdefault("DB_CONN_STR",        "postgresql://mock:mock@127.0.0.1:5432/mock")
os.environ.setdefault("BROKER_SECRET",      "test-secret-abc123")
os.environ.setdefault("DOMAIN_CONFIG_PATH", DOMAIN_CONFIG_PATH)
os.environ.setdefault("BROKER_PORT",        "8083")

# Mock psycopg2.connect before importing main so no real DB call is made
mock_cursor  = MagicMock()
mock_conn    = MagicMock()
mock_cursor.__enter__ = lambda s: s
mock_cursor.__exit__  = MagicMock(return_value=False)
mock_conn.cursor.return_value = mock_cursor
mock_conn.__enter__ = lambda s: s
mock_conn.__exit__  = MagicMock(return_value=False)

# Simulate UPSERT returning (id=1, inserted=True)
mock_cursor.fetchone.return_value = (1, True)

with patch("psycopg2.connect", return_value=mock_conn):
    import main as broker_main
    from fastapi.testclient import TestClient
    client = TestClient(broker_main.app)

AUTH  = {"Authorization": "Bearer test-secret-abc123"}
NOAUTH= {"Authorization": "Bearer wrong-secret"}

# ── /health ──────────────────────────────────────────────────────────────────
r = client.get("/health")
if r.status_code == 200 and r.json()["status"] == "running":
    ok("/health  →  200 running")
else:
    fail("/health", str(r.json()))

domains_in_health = r.json().get("canonical_domains", [])
expected_count = len(json.load(open(DOMAIN_CONFIG_PATH))["domains"])
if len(domains_in_health) == expected_count:
    ok(f"/health lists all {expected_count} canonical domains")
else:
    fail(f"/health domain count: {len(domains_in_health)} (expected {expected_count})")

# ── /ingest auth guard ────────────────────────────────────────────────────────
with patch("psycopg2.connect", return_value=mock_conn):
    r = client.post("/ingest", json={"table": "datasets", "action": "UPSERT",
                                     "record": {"name": "X"}}, headers=NOAUTH)
if r.status_code == 401:
    ok("/ingest  wrong token  →  401")
else:
    fail("/ingest auth guard", f"got {r.status_code}")

# ── /ingest UPSERT dataset ────────────────────────────────────────────────────
payload = {
    "table": "datasets",
    "action": "UPSERT",
    "record": {
        "name":       "M3 Competition",
        "domain":     "Economics",
        "source_url": "https://example.com/m3",
        "metadata": {
            "slug":        "m3-competition",
            "timePoints":  "3003",
            "interval":    "Monthly",
            "variables":   "1",
            "dimensions":  "1",
            "description": "Classic M3 forecasting competition.",
            "paperLink":   "",
            "benchmarks":  {"Darts": True},
        },
    },
}

with patch("psycopg2.connect", return_value=mock_conn):
    r = client.post("/ingest", json=payload, headers=AUTH)

if r.status_code == 200:
    body = r.json()
    ok(f'/ingest UPSERT dataset  →  200  status={body["status"]}')
    if body.get("domain_canonical") == "Economics":
        ok(f'  domain_canonical  =  {body["domain_canonical"]}')
    else:
        fail("  domain_canonical wrong", str(body))
    if body.get("domain_image") == "pics/domains/economics.jpg":
        ok(f'  domain_image      =  {body["domain_image"]}')
    else:
        fail("  domain_image wrong", str(body))
else:
    fail(f"/ingest UPSERT dataset", f"status={r.status_code}  body={r.text}")

# ── /ingest UPSERT model (domain from metadata.dominantDomain) ───────────────
model_payload = {
    "table": "models",
    "action": "UPSERT",
    "record": {
        "name":         "PatchTST",
        "architecture": "Transformer",
        "source_url":   "https://arxiv.org/abs/2211.14730",
        "metadata": {
            "description":   "Patch-based time series transformer.",
            "datasetsCount": 8,
            "dominantDomain": "Energy",
        },
    },
}

with patch("psycopg2.connect", return_value=mock_conn):
    r = client.post("/ingest", json=model_payload, headers=AUTH)

if r.status_code == 200:
    body = r.json()
    ok(f'/ingest UPSERT model  →  200  status={body["status"]}')
    if body.get("domain_canonical") == "Energy":
        ok(f'  domain_canonical from dominantDomain  =  {body["domain_canonical"]}')
    else:
        fail("  model domain_canonical wrong", str(body))
else:
    fail("/ingest UPSERT model", f"status={r.status_code}  body={r.text}")

# ── /ingest DELETE ────────────────────────────────────────────────────────────
mock_cursor.rowcount = 1
del_payload = {"table": "datasets", "action": "DELETE",
               "record": {"name": "M3 Competition"}}
with patch("psycopg2.connect", return_value=mock_conn):
    r = client.post("/ingest", json=del_payload, headers=AUTH)

if r.status_code == 200 and r.json().get("action") == "DELETE":
    ok(f'/ingest DELETE  →  200')
else:
    fail("/ingest DELETE", f"status={r.status_code}  body={r.text}")

# ── /ingest/batch ─────────────────────────────────────────────────────────────
batch_payload = {
    "records": [
        {"table": "datasets", "action": "UPSERT",
         "record": {"name": "ETTh1", "domain": "Energy",
                    "metadata": {"slug": "etth1", "timePoints": "17420",
                                 "interval": "Hourly", "variables": "7",
                                 "dimensions": "7", "description": "Electricity transformer.",
                                 "paperLink": "", "benchmarks": {"Darts": True}}}},
        {"table": "datasets", "action": "UPSERT",
         "record": {"name": "AirPassengersDataset", "domain": "Transportation",
                    "metadata": {"slug": "airpassengers", "timePoints": "144",
                                 "interval": "Monthly", "variables": "1",
                                 "dimensions": "1", "description": "Airline passengers.",
                                 "paperLink": "", "benchmarks": {}}}},
    ]
}
mock_cursor.fetchone.return_value = (1, True)
with patch("psycopg2.connect", return_value=mock_conn):
    r = client.post("/ingest/batch", json=batch_payload, headers=AUTH)

if r.status_code == 200:
    body = r.json()
    ok(f'/ingest/batch  →  200  total={body["total"]} inserted={body["inserted"]}')
    for res in body["results"]:
        ok(f'  {res["name"]}  canonical={res.get("domain_canonical")}  image={res.get("domain_image")}')
else:
    fail("/ingest/batch", f"status={r.status_code}  body={r.text}")

# ── /ingest missing name ──────────────────────────────────────────────────────
with patch("psycopg2.connect", return_value=mock_conn):
    r = client.post("/ingest",
                    json={"table": "datasets", "action": "UPSERT",
                          "record": {"domain": "Energy"}},
                    headers=AUTH)
if r.status_code == 422:
    ok("/ingest missing name  →  422 validation error")
else:
    fail("/ingest missing name validation", f"got {r.status_code}")


# ═════════════════════════════════════════════════════════════════════════════
# 3. Live DB test (only when LIVE_DB=1)
# ═════════════════════════════════════════════════════════════════════════════

if os.environ.get("LIVE_DB") == "1":
    section("3 · Live DB integration (Cloud SQL via proxy)")
    import psycopg2 as _pg
    conn_str = os.environ.get("DB_CONN_STR", "")
    try:
        conn = _pg.connect(conn_str)
        conn.close()
        ok("Connected to Cloud SQL successfully")

        # Reset broker's module-level connection factory to use real DB
        import importlib
        importlib.reload(broker_main)
        real_client = TestClient(broker_main.app)

        live_payload = {
            "table": "datasets",
            "action": "UPSERT",
            "record": {
                "name":       "_BrokerTestDataset_DELETE_ME",
                "domain":     "Sensor Network",
                "source_url": "https://example.com/brokertest",
                "metadata": {
                    "slug":        "broker-test-dataset-delete-me",
                    "timePoints":  "1000",
                    "interval":    "Seconds",
                    "variables":   "3",
                    "dimensions":  "3",
                    "description": "Automated broker test — safe to delete.",
                    "paperLink":   "",
                    "benchmarks":  {},
                },
            },
        }
        r = real_client.post("/ingest", json=live_payload,
                             headers={"Authorization": f"Bearer {os.environ['BROKER_SECRET']}"})
        if r.status_code == 200:
            body = r.json()
            ok(f'Live UPSERT  →  status={body["status"]}  '
               f'canonical={body["domain_canonical"]}  image={body["domain_image"]}')

            # Verify row landed in DB
            conn = _pg.connect(conn_str)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT name, domain_canonical, domain_image FROM datasets "
                    "WHERE name = '_BrokerTestDataset_DELETE_ME'"
                )
                row = cur.fetchone()
            conn.close()
            if row:
                ok(f'Row in DB: name={row[0]}  canonical={row[1]}  image={row[2]}')
            else:
                fail("Row not found in DB after upsert")

            # Clean up
            r2 = real_client.post("/ingest",
                                  json={"table": "datasets", "action": "DELETE",
                                        "record": {"name": "_BrokerTestDataset_DELETE_ME"}},
                                  headers={"Authorization": f"Bearer {os.environ['BROKER_SECRET']}"})
            if r2.status_code == 200:
                ok("Cleanup DELETE  →  200")
        else:
            fail("Live UPSERT", f"{r.status_code}  {r.text}")

    except _pg.OperationalError as e:
        fail("Cannot connect to Cloud SQL", str(e))
        print(f"\n  {YELLOW}Hint: start the Cloud SQL proxy first:{RESET}")
        print("  cloud-sql-proxy project-4896a6b8-11ce-4f5a-ac4:us-east4:free-trial-first-project --port=5432")


# ═════════════════════════════════════════════════════════════════════════════
# Summary
# ═════════════════════════════════════════════════════════════════════════════

total = passed + failed
print(f"\n{'═' * 60}")
print(f"{BOLD}Results: {GREEN}{passed} passed{RESET}{BOLD}, {RED if failed else ''}{failed} failed{RESET}{BOLD} / {total} total{RESET}")
if failed == 0:
    print(f"{GREEN}{BOLD}All tests passed.{RESET}")
else:
    print(f"{RED}{BOLD}Some tests failed — see above.{RESET}")
print()
sys.exit(0 if failed == 0 else 1)
