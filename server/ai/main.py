"""
Time Series Commons — AI Assistant Service

Provides a chat API backed by Google Gemini (gemini-3-flash-preview).
The full dataset catalog is embedded in the system instruction on every
request, which makes implicit caching effective (Gemini automatically
caches repeated prefixes at no extra cost on the free tier).

Users can upload their own documents (PDFs, text, CSV) which are stored
via the Gemini Files API and included as file parts in the conversation.

Note on caching
---------------
Explicit context caching requires a paid Gemini plan (free tier quota = 0).
We instead rely on Gemini's implicit caching: identical system instruction
prefixes sent in quick succession are automatically cached server-side with
no developer action required.  The catalog JSON (~125K tokens) qualifies
(min threshold for gemini-3-flash-preview is 1024 tokens).

Endpoints
---------
GET  /                  Health check
POST /session/new       Start a new user session → {session_id}
POST /upload            Upload a file to a session → {filename, session_id}
POST /chat              Send a message → {response, sources, usage}
DELETE /session         Clean up a session's uploaded files

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
MODEL = "models/gemini-3-flash-preview"

# ---------------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------------

client = genai.Client(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Catalog data (loaded once at startup)
# ---------------------------------------------------------------------------

def load_catalog() -> tuple[list[dict], str]:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)

    entries: list[dict] = raw.get("models", [])

    domains = sorted({e.get("domain", "General") for e in entries})
    benchmarks: set[str] = set()
    for e in entries:
        benchmarks.update(e.get("benchmarks", {}).keys())

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
# System instruction (sent on every request; implicit caching applies)
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
# Per-session state
# ---------------------------------------------------------------------------
# sessions: { session_id: { file_uris: [...], created_at, last_active } }

sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


def _session_cleanup_loop() -> None:
    """Background thread: removes sessions idle for more than 2 hours."""
    while True:
        time.sleep(300)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
        with _sessions_lock:
            stale = [
                sid for sid, s in sessions.items()
                if s["last_active"] < cutoff
            ]
            for sid in stale:
                # Delete uploaded files from Gemini Files API
                for uri in sessions[sid].get("file_uris", []):
                    try:
                        # Extract file name from URI for deletion
                        file_name = uri.split("/")[-1] if "/" in uri else uri
                        client.files.delete(name=f"files/{file_name}")
                    except Exception:
                        pass
                del sessions[sid]
                log.info(f"Evicted stale session {sid[:8]}")


# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)


@app.route("/")
def health():
    return jsonify({
        "status":          "running",
        "model":           MODEL,
        "catalog_entries": len(catalog_entries),
        "active_sessions": len(sessions),
    }), 200


@app.route("/session/new", methods=["POST"])
def session_new():
    """Create a new user session."""
    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    with _sessions_lock:
        sessions[session_id] = {
            "file_uris":   [],
            "file_names":  [],  # Gemini file resource names for deletion
            "created_at":  now,
            "last_active": now,
        }
    log.info(f"New session: {session_id[:8]}")
    return jsonify({"session_id": session_id}), 200


@app.route("/upload", methods=["POST"])
def upload():
    """
    Upload a file to a session via the Gemini Files API.
    The file URI is stored in the session and included in subsequent chat calls.

    Form fields: session_id (string), file (multipart)
    Returns:     {session_id, filename, mime_type, file_count}
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

    ext = pathlib.Path(filename).suffix.lower()
    mime_map = {
        ".pdf":  "application/pdf",
        ".txt":  "text/plain",
        ".md":   "text/plain",
        ".csv":  "text/plain",
        ".json": "application/json",
    }
    mime_type = mime_map.get(ext, "application/octet-stream")

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

        # Wait for processing
        for _ in range(30):
            status = client.files.get(name=gemini_file.name)
            if status.state.name != "PROCESSING":
                break
            time.sleep(2)

        if status.state.name != "ACTIVE":
            return jsonify({"error": f"File processing failed: {status.state.name}"}), 500

        file_uri  = gemini_file.uri
        file_name = gemini_file.name
        log.info(f"File ready: {file_uri}")

    except Exception as e:
        log.error(f"File upload failed: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        os.unlink(tmp_path)

    with _sessions_lock:
        sessions[session_id]["file_uris"].append(file_uri)
        sessions[session_id]["file_names"].append(file_name)
        sessions[session_id]["last_active"] = datetime.now(timezone.utc)
        file_count = len(sessions[session_id]["file_uris"])

    return jsonify({
        "session_id": session_id,
        "filename":   filename,
        "mime_type":  mime_type,
        "file_count": file_count,
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

    file_uris: list[str] = session.get("file_uris", [])

    # Build conversation contents
    history_raw: list[dict] = body.get("history", [])
    contents: list[types.Content] = []

    for turn in history_raw:
        role    = turn.get("role", "user")
        content = turn.get("content", "")
        contents.append(
            types.Content(role=role, parts=[types.Part(text=content)])
        )

    # Build current user message — always include uploaded file URIs so the
    # model can reference them regardless of when they were uploaded.
    # The Gemini Files API stores files server-side; we only pass URI references.
    user_parts: list[types.Part] = []
    for uri in file_uris:
        user_parts.append(types.Part(file_data=types.FileData(file_uri=uri)))
    user_parts.append(types.Part(text=message))

    contents.append(types.Content(role="user", parts=user_parts))

    try:
        resp = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
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

    # Extract dataset names mentioned in the response
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
    """Clean up a session and its uploaded files."""
    body = request.get_json(silent=True) or {}
    session_id = body.get("session_id")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400

    with _sessions_lock:
        session = sessions.pop(session_id, None)

    if not session:
        return jsonify({"status": "not_found"}), 404

    for name in session.get("file_names", []):
        try:
            client.files.delete(name=name)
        except Exception:
            pass

    return jsonify({"status": "deleted"}), 200


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    threading.Thread(target=_session_cleanup_loop, daemon=True).start()
    log.info(f"AI assistant service starting on port {PORT}")
    log.info(f"Catalog: {len(catalog_entries)} datasets loaded from {DATA_PATH}")
    app.run(host="0.0.0.0", port=PORT)
