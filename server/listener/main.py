"""
Time Series Commons — Catalog Listener Service

Connects to PostgreSQL and subscribes to the 'catalog_updates' NOTIFY channel.
When a row changes (INSERT or UPDATE on datasets or models), it compares a
hash of the payload against the last-known state. If a real change is detected
it POSTs a minimal update payload to the website updater endpoint.

Design mirrors the IndyCar anomaly detection architecture from Indiana University:
  - Persistent TCP-like connection (LISTEN/NOTIFY)   ≈ MQTT broker subscription
  - select() non-blocking I/O wait                   ≈ Storm spout polling
  - Hash diff gate                                   ≈ HTM anomaly filter
  - POST to site updater                             ≈ WebSocket broadcast

Start:
    python main.py          (reads .env in cwd or parent)

Managed by: /etc/systemd/system/timeseries-listener.service
"""

import os
import json
import select
import hashlib
import threading
import logging
import time
import requests
import psycopg2
import psycopg2.extensions
from flask import Flask, jsonify
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

app = Flask(__name__)

DB_CONN_STR     = os.environ["DB_CONN_STR"]
SITE_UPDATE_URL = os.environ["SITE_UPDATE_URL"]
PORT            = int(os.environ.get("LISTENER_PORT", 8080))

# ---------------------------------------------------------------------------
# In-memory hash store
# Key:   "tablename:id"   e.g. "datasets:42"
# Value: md5 hex digest of the last-seen notification payload
# ---------------------------------------------------------------------------
site_state: dict[str, str] = {}


def compute_hash(payload: dict) -> str:
    """Stable, deterministic hash of a notification payload dict."""
    return hashlib.md5(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()


def handle_update(payload_str: str) -> None:
    """
    Called once per pg_notify message on 'catalog_updates'.

    Checks whether the incoming payload represents a genuine change from the
    last recorded state. If not, the notification is silently dropped (no
    site update, no wasted HTTP call). This is the hash-diff gate.
    """
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        log.error(f"Could not parse notify payload: {payload_str!r}")
        return

    key      = f"{payload['table']}:{payload['id']}"
    new_hash = compute_hash(payload)

    if site_state.get(key) == new_hash:
        log.info(f"[SKIP] {key} — payload hash unchanged, no site update needed")
        return

    site_state[key] = new_hash
    log.info(f"[CHANGE] {key} — action={payload['action']}, pushing update to site")

    try:
        resp = requests.post(
            SITE_UPDATE_URL,
            json=payload,
            timeout=10
        )
        resp.raise_for_status()
        log.info(f"[OK] Site update accepted for {key} — HTTP {resp.status_code}")
    except requests.RequestException as e:
        log.error(f"[FAIL] Site update POST failed for {key}: {e}")


def listener_loop() -> None:
    """
    Long-running background thread: maintains a single LISTEN connection to
    PostgreSQL and dispatches incoming notifications to handle_update().

    Uses select() for efficient I/O multiplexing — never busy-polls.
    Automatically reconnects with backoff on connection loss or unexpected error.
    """
    while True:
        conn = None
        try:
            log.info("Connecting to PostgreSQL for LISTEN ...")
            conn = psycopg2.connect(DB_CONN_STR)
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)

            with conn.cursor() as cur:
                cur.execute("LISTEN catalog_updates;")

            log.info("Listening on channel: catalog_updates")

            while True:
                # Block for up to 30 s; wake immediately if the socket is readable
                ready = select.select([conn], [], [], 30)
                if ready[0]:
                    conn.poll()
                    while conn.notifies:
                        notify = conn.notifies.pop(0)
                        log.debug(f"Raw notify: {notify.payload!r}")
                        handle_update(notify.payload)

        except psycopg2.OperationalError as e:
            log.error(f"DB connection lost: {e}. Reconnecting in 10 s ...")
            time.sleep(10)
        except Exception as e:
            log.error(f"Unexpected error in listener loop: {e}. Reconnecting in 10 s ...")
            time.sleep(10)
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Flask health / debug API
# ---------------------------------------------------------------------------

@app.route("/")
def health():
    """Health check — returns running status and number of tracked rows."""
    return jsonify({
        "status":       "running",
        "tracked_rows": len(site_state),
    }), 200


@app.route("/state")
def state():
    """Returns the current in-memory hash state for all tracked rows."""
    return jsonify(site_state), 200


@app.route("/flush", methods=["POST"])
def flush():
    """
    Clears the hash state so every subsequent notify triggers a site update,
    regardless of whether the payload has changed. Useful after a site redeploy
    or when the in-memory state has drifted from actual site content.
    """
    site_state.clear()
    log.info("Hash state flushed — all rows will be treated as new on next notify")
    return jsonify({"status": "flushed"}), 200


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    t = threading.Thread(target=listener_loop, daemon=True)
    t.start()
    log.info(f"Flask health API starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT)
