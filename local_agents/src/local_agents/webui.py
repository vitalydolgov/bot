import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .store import (
    connect,
    create_session,
    enqueue,
    find_session,
    get_agent,
    is_turn_running,
    latest_session,
    read_events,
    session_sdk_id,
)

WEBUI_DIR = Path(__file__).parent / "webui"
WEBUI_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "application/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


class WebuiState:
    def __init__(self, agent: str, session_id: str) -> None:
        self.agent = agent
        self.session_id = session_id
        self.lock = threading.Lock()


def make_handler(state: WebuiState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_json(self, obj, status=200):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def read_json(self):
            length = int(self.headers.get("Content-Length") or 0)
            if length == 0:
                return {}
            return json.loads(self.rfile.read(length))

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path in WEBUI_FILES:
                name, content_type = WEBUI_FILES[parsed.path]
                body = (WEBUI_DIR / name).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif parsed.path == "/api/session":
                with state.lock:
                    session_id = state.session_id
                conn = connect()
                try:
                    sdk_id = session_sdk_id(conn, session_id)
                finally:
                    conn.close()
                self.send_json({"agent": state.agent, "session_id": session_id, "sdk_id": sdk_id})
            elif parsed.path == "/api/events":
                after = int(parse_qs(parsed.query).get("after", ["0"])[0])
                with state.lock:
                    session_id = state.session_id
                conn = connect()
                try:
                    events = read_events(conn, session_id, after)
                    busy = is_turn_running(conn, session_id)
                finally:
                    conn.close()
                self.send_json({
                    "busy": busy,
                    "events": [
                        {"id": e["id"], "kind": e["kind"], "payload": e["payload"]}
                        for e in events
                    ]
                })
            else:
                self.send_json({"error": "not found"}, 404)

        def do_POST(self):
            parsed = urlparse(self.path)
            if parsed.path == "/api/message":
                data = self.read_json()
                text = (data.get("text") or "").strip()
                if not text:
                    self.send_json({"error": "empty message"}, 400)
                    return
                with state.lock:
                    session_id = state.session_id
                conn = connect()
                try:
                    enqueue(conn, session_id, "message", {"text": text})
                finally:
                    conn.close()
                self.send_json({"ok": True})
            elif parsed.path == "/api/cancel":
                with state.lock:
                    session_id = state.session_id
                conn = connect()
                try:
                    enqueue(conn, session_id, "cancel", {})
                finally:
                    conn.close()
                self.send_json({"ok": True})
            elif parsed.path == "/api/new":
                with state.lock:
                    old_session_id = state.session_id
                    conn = connect()
                    try:
                        enqueue(conn, old_session_id, "detach", {})
                        state.session_id = create_session(conn, state.agent)
                        session_id = state.session_id
                    finally:
                        conn.close()
                self.send_json({"session_id": session_id})
            else:
                self.send_json({"error": "not found"}, 404)

    return Handler


def webui(agent_name: str, port: int, new: bool, resume_ref: str | None) -> int:
    conn = connect()
    if get_agent(conn, agent_name) is None:
        print(f"No agent named {agent_name}. Start it with `uv run local-agents serve`.")
        conn.close()
        return 1
    resumed = False
    if resume_ref is not None:
        row = find_session(conn, resume_ref)
        if row is None:
            print(f"No session {resume_ref}.")
            conn.close()
            return 1
        session_id = row["id"]
        enqueue(conn, session_id, "resume", {})
        resumed = True
    elif not new:
        row = latest_session(conn, agent_name)
        if row is not None:
            session_id = row["id"]
            enqueue(conn, session_id, "resume", {})
            resumed = True
    if not resumed:
        session_id = create_session(conn, agent_name)
    conn.close()

    state = WebuiState(agent_name, session_id)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(state))
    conn = connect()
    try:
        shown = session_sdk_id(conn, session_id) or session_id
    finally:
        conn.close()
    where = f"Resuming session {shown}" if resumed else f"Talking to {agent_name} (session {shown})"
    print(f"{where}.")
    print(f"Serving the webui at http://127.0.0.1:{port}/ — Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        conn = connect()
        try:
            enqueue(conn, state.session_id, "detach", {})
        finally:
            conn.close()
    return 0
