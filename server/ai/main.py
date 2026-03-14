"""
Time Series Commons — AI Assistant Service

Provides a chat API backed by Google Gemini (gemini-3-flash-preview) with
explicit context caching for the full dataset catalog.  Users can also upload
their own documents (PDFs, text, CSV) which are added to a per-session cache
so the model has full context while answering.

Intended use-case: help researchers discover the right time series datasets
and benchmark models for their project.

Caching strategy
----------------
• Global catalog cache  — created at startup from data/models.json + system
                          prompt.  Shared by every user.  TTL 1 hour, silently
                          refreshed by a background thread when < 5 min remain.
• Per-session cache     — created by POST /session/new.  Contains the catalog
                          cache contents PLUS any user-uploaded files.
                          Stored in an in-memory sessions dict keyed by UUID.
                          TTL 1 hour, refreshed on each /chat call.

Endpoints
---------
GET  /                  Health check + cache status
POST /session/new       Start a new user session → {session_id}
POST /upload            Upload a file to a session → {filename, session_id}
POST /chat              Send a message → {response, sources, usage}
DELETE /session         Clean up a session and its Gemini cache

Start:
    python main.py      (reads .env in cwd)

Managed by: /etc/systemd/system/timeseries-ai.service
"""

import json
import logging
import os
import pathlib
import re
import tempfile
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from google import genai
from google.genai import types

load_dotenv()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PORT           = int(os.environ.get("FLASK_PORT", 8082))
DATA_PATH      = os.environ.get(
    "DATA_PATH",
    str(pathlib.Path(__file__).resolve().parents[2] / "data" / "models.json"),
)
MODEL          = "models/gemini-3-flash-preview"
CACHE_TTL      = "3600s"   # 1 hour
CACHE_REFRESH_THRESHOLD = 300   # refresh when < 5 min remain (seconds)

# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

client = genai.Client(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Catalog data (loaded once at startup)
# ---------------------------------------------------------------------------

def load_catalog() -> tuple[list[dict], str]:
    """
    Reads data/models.json and returns (entries_list, summary_string).
    The summary is injected into the cached system instruction.
    """
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    entries: list[dict] = raw.get("models", [])

    # Compute stats for the summary header
    domains = sorted({e.get("domain", "General") for e in entries})
    benchmarks: set[str] = set()
    for e in entries:
        benchmarks.update(k for k, v in e.get("benchmarks", {}).items() if v)

    summary = (
        f"Total datasets: {len(entries)}\n"
        f"Domains ({len(domains)}): {', '.join(domains)}\n"
        f"Benchmark frameworks: {', '.join(sorted(benchmarks))}\n"
    )
    log.info(
        f"Catalog loaded: {len(entries)} datasets, "
        f"{len(domains)} domains, {len(benchmarks)} benchmarks"
    )
    return entries, summary


catalog_entries, catalog_summary = load_catalog()

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_INSTRUCTION = f"""You are an expert research assistant for the Time Series Commons \
— a curated catalog maintained by the UVA MLSys research group (Dr. Judy Fox).

Your primary role is to help researchers and practitioners find the right time series \
datasets and benchmark models for their projects.  When a user describes their work or \
uploads a document, carefully analyze their requirements and recommend specific, \
well-matched datasets from the catalog below.

{catalog_summary}

FULL CATALOG (JSON):
{json.dumps(catalog_entries, ensure_ascii=False)}

RESPONSE GUIDELINES:
- Recommend datasets by their exact "name" field from the catalog.
- For each recommendation, explain clearly WHY it fits the user's use case \
(domain match, number of variables, time points, interval, description).
- Mention which benchmark frameworks have evaluated on the dataset \
(from the "benchmarks" map — list only the ones marked true).
- If the user uploads a document, analyze it to understand their project and \
tailor recommendations accordingly.
- When relevant, suggest the user visit the full catalog at models.html.
- Be concise but thorough; use bullet points for dataset lists.
- If you are unsure or no dataset fits well, say so honestly.
"""

# ---------------------------------------------------------------------------
# Global catalog cache
# ---------------------------------------------------------------------------

_catalog_cache_name: str | None = None
_catalog_cache_expire: datetime | None = None
_catalog_cache_lock = threading.Lock()


def _create_catalog_cache() -> str:
    """Create (or recreate) the shared global catalog cache on Gemini."""
    log.info("Creating global catalog cache on Gemini ...")
    cache = client.caches.create(
        model=MODEL,
        config=types.CreateCachedContentConfig(
            display_name="timeseries-commons-catalog",
            system_instruction=SYSTEM_INSTRUCTION,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part(text="[Catalog context loaded. Ready to assist.]")],
                )
            ],
            ttl=CACHE_TTL,
        ),
    )
    expire = datetime.now(timezone.utc) + timedelta(seconds=3600)
    log.info(f"Global catalog cache created: {cache.name} (expires ~{expire.isoformat()})")
    return cache.name, expire


def ensure_catalog_cache() -> str:
    """Return the current catalog cache name, refreshing if close to expiry."""
    global _catalog_cache_name, _catalog_cache_expire
    with _catalog_cache_lock:
        now = datetime.now(timezone.utc)
        needs_refresh = (
            _catalog_cache_name is None
            or _catalog_cache_expire is None
            or (_catalog_cache_expire - now).total_seconds() < CACHE_REFRESH_THRESHOLD
        )
        if needs_refresh:
            _catalog_cache_name, _catalog_cache_expire = _create_catalog_cache()
        return _catalog_cache_name


def _cache_refresh_loop() -> None:
    """Background thread: checks every minute and refreshes the catalog cache."""
    while True:
        time.sleep(60)
        try:
            ensure_catalog_cache()
        except Exception as e:
            log.error(f"Cache refresh error: {e}")


# ---------------------------------------------------------------------------
# Per-session state
# ---------------------------------------------------------------------------
# sessions: { session_id: { cache_name, file_uris: [...], created_at, last_active } }

sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


def _build_session_cache(session_id: str, file_uris: list[str]) -> str:
    """
    Create a Gemini cache for a user session that includes the catalog
    system instruction AND any files the user has uploaded.
    """
    contents = [
        types.Content(
            role="user",
            parts=[types.Part(text="[Catalog context loaded. Ready to assist.]")],
        )
    ]

    # Add uploaded user files
    for uri in file_uris:
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(file_data=types.FileData(file_uri=uri))],
            )
        )

    cache = client.caches.create(
        model=MODEL,
        config=types.CreateCachedContentConfig(
            display_name=f"ts-session-{session_id[:8]}",
            system_instruction=SYSTEM_INSTRUCTION,
            contents=contents,
            ttl=CACHE_TTL,
        ),
    )
    log.info(
        f"Session cache created: {cache.name} "
        f"(session={session_id[:8]}, files={len(file_uris)})"
    )
    return cache.name


def _delete_cache_safe(cache_name: str) -> None:
    """Delete a Gemini cache, ignoring errors (cache may have already expired)."""
    try:
        client.caches.delete(cache_name)
        log.info(f"Deleted cache: {cache_name}")
    except Exception as e:
        log.warning(f"Could not delete cache {cache_name}: {e}")


def _session_cleanup_loop() -> None:
    """Background thread: removes sessions idle for more than 90 minutes."""
    while True:
        time.sleep(300)
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=90)
        with _sessions_lock:
            stale = [
                sid for sid, s in sessions.items()
                if s["last_active"] < cutoff
            ]
            for sid in stale:
                _delete_cache_safe(sessions[sid]["cache_name"])
                del sessions[sid]
                log.info(f"Evicted stale session {sid[:8]}")


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)


@app.route("/")
def health():
    cache_ok = _catalog_cache_name is not None
    return jsonify({
        "status":          "running",
        "model":           MODEL,
        "catalog_cache":   _catalog_cache_name,
        "catalog_entries": len(catalog_entries),
        "active_sessions": len(sessions),
        "cache_expires":   _catalog_cache_expire.isoformat() if _catalog_cache_expire else None,
    }), 200


@app.route("/session/new", methods=["POST"])
def session_new():
    """
    Create a new user session with a fresh per-session Gemini cache
    (initially identical to the global catalog cache but session-scoped
    so user uploads can be added later without affecting other users).
    """
    session_id = str(uuid.uuid4())
    try:
        cache_name = _build_session_cache(session_id, [])
    except Exception as e:
        log.error(f"Failed to create session cache: {e}")
        return jsonify({"error": str(e)}), 500

    now = datetime.now(timezone.utc)
    with _sessions_lock:
        sessions[session_id] = {
            "cache_name":  cache_name,
            "file_uris":   [],
            "created_at":  now,
            "last_active": now,
        }

    log.info(f"New session: {session_id[:8]}")
    return jsonify({"session_id": session_id}), 200


@app.route("/upload", methods=["POST"])
def upload():
    """
    Upload a file to a session.  The file is sent to the Gemini Files API,
    then the session cache is recreated to include it.

    Form fields: session_id (string), file (multipart)
    Returns:     {session_id, filename, mime_type}
    """
    session_id = request.form.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    with _sessions_lock:
        session = sessions.get(session_id)
    if not session:
        return jsonify({"error": "session not found — start a new session first"}), 404

    if "file" not in request.files:
        return jsonify({"error": "file field required"}), 400

    uploaded = request.files["file"]
    filename  = uploaded.filename or "upload"

    # Detect MIME type from extension
    ext = pathlib.Path(filename).suffix.lower()
    mime_map = {
        ".pdf":  "application/pdf",
        ".txt":  "text/plain",
        ".md":   "text/plain",
        ".csv":  "text/plain",
        ".json": "application/json",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

    # Save to temp file and upload to Gemini Files API
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        uploaded.save(tmp.name)
        tmp_path = tmp.name

    try:
        log.info(f"Uploading {filename} ({mime_type}) to Gemini Files API ...")
        gemini_file = client.files.upload(
            file=tmp_path,
            config=types.UploadFileConfig(
                display_name=filename,
                mime_type=mime_type,
            ),
        )

        # Wait for processing to complete
        for _ in range(30):
            status = client.files.get(name=gemini_file.name)
            if status.state.name != "PROCESSING":
                break
            time.sleep(2)

        if status.state.name != "ACTIVE":
            return jsonify({"error": f"File processing failed: {status.state.name}"}), 500

        file_uri = gemini_file.uri
        log.info(f"File ready: {file_uri}")

    except Exception as e:
        log.error(f"File upload failed: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        os.unlink(tmp_path)

    # Rebuild session cache to include the new file
    with _sessions_lock:
        old_cache = sessions[session_id]["cache_name"]
        new_file_uris = sessions[session_id]["file_uris"] + [file_uri]

    try:
        new_cache_name = _build_session_cache(session_id, new_file_uris)
    except Exception as e:
        log.error(f"Failed to rebuild session cache: {e}")
        return jsonify({"error": str(e)}), 500

    # Swap cache atomically
    with _sessions_lock:
        sessions[session_id]["cache_name"]  = new_cache_name
        sessions[session_id]["file_uris"]   = new_file_uris
        sessions[session_id]["last_active"] = datetime.now(timezone.utc)
    _delete_cache_safe(old_cache)

    return jsonify({
        "session_id": session_id,
        "filename":   filename,
        "mime_type":  mime_type,
        "file_count": len(new_file_uris),
    }), 200


@app.route("/chat", methods=["POST"])
def chat():
    """
    Send a user message and receive an AI response.

    Request JSON:
        session_id  str
        message     str
        history     [{role: "user"|"model", content: str}, ...]   (optional)

    Response JSON:
        response    str
        sources     [str]   dataset names mentioned in the response
        usage       {cached_tokens, total_tokens}
    """
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id")
    message    = body.get("message", "").strip()

    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    if not message:
        return jsonify({"error": "message required"}), 400

    with _sessions_lock:
        session = sessions.get(session_id)
    if not session:
        return jsonify({"error": "session not found — start a new session first"}), 404

    cache_name = session["cache_name"]

    # Build conversation history for Gemini
    history_raw: list[dict] = body.get("history", [])
    contents: list[types.Content] = []
    for turn in history_raw:
        role    = turn.get("role", "user")
        content = turn.get("content", "")
        contents.append(
            types.Content(role=role, parts=[types.Part(text=content)])
        )
    # Append current user message
    contents.append(
        types.Content(role="user", parts=[types.Part(text=message)])
    )

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                cached_content=cache_name,
            ),
        )
    except Exception as e:
        log.error(f"Gemini generate_content failed: {e}")
        return jsonify({"error": str(e)}), 500

    # Update last_active
    with _sessions_lock:
        if session_id in sessions:
            sessions[session_id]["last_active"] = datetime.now(timezone.utc)

    response_text = resp.text or ""

    # Extract dataset names mentioned in the response by matching against catalog
    catalog_names = {e["name"] for e in catalog_entries}
    sources = sorted({
        name for name in catalog_names
        if re.search(r"\b" + re.escape(name) + r"\b", response_text, re.IGNORECASE)
    })

    # Usage metadata
    usage = {}
    if resp.usage_metadata:
        usage = {
            "cached_tokens": getattr(resp.usage_metadata, "cached_content_token_count", 0),
            "total_tokens":  getattr(resp.usage_metadata, "total_token_count", 0),
        }

    return jsonify({
        "response": response_text,
        "sources":  sources,
        "usage":    usage,
    }), 200


@app.route("/session", methods=["DELETE"])
def session_delete():
    """
    Clean up a session: delete the Gemini cache and remove from memory.
    Request JSON: {session_id: str}
    """
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    with _sessions_lock:
        session = sessions.pop(session_id, None)

    if not session:
        return jsonify({"status": "not_found"}), 404

    _delete_cache_safe(session["cache_name"])
    return jsonify({"status": "deleted"}), 200


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Create the global catalog cache before accepting requests
    ensure_catalog_cache()

    # Background threads
    threading.Thread(target=_cache_refresh_loop,   daemon=True).start()
    threading.Thread(target=_session_cleanup_loop, daemon=True).start()

    log.info(f"AI assistant service starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT)
