import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .store import (
    connect,
    create_session,
    enqueue,
    find_session,
    get_agent,
    latest_session,
    read_events,
    session_sdk_id,
)

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>local-agents</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; background: #1e1e1e; color: #d4d4d4; display: flex; flex-direction: column; height: 100vh; }
  header { display: flex; align-items: center; gap: 12px; padding: 10px 16px; border-bottom: 1px solid #333; font-size: 13px; }
  header .title { font-weight: bold; color: #fff; }
  header .meta { color: #888; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  header button { margin-left: auto; background: #2d2d2d; color: #d4d4d4; border: 1px solid #444; border-radius: 4px; padding: 4px 10px; cursor: pointer; font: inherit; }
  header button:hover { background: #3a3a3a; }
  #log { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 8px; }
  .msg { max-width: 80ch; padding: 8px 12px; border-radius: 6px; white-space: pre-wrap; word-wrap: break-word; line-height: 1.4; }
  .user { align-self: flex-end; background: #264f78; color: #fff; }
  .assistant { align-self: flex-start; background: #2d2d2d; }
  .event { align-self: flex-start; color: #888; font-size: 14px; padding: 0 4px; }
  .event.error { color: #f48771; }
  form { display: flex; gap: 8px; padding: 12px 16px; border-top: 1px solid #333; }
  input[type=text] { flex: 1; background: #2d2d2d; border: 1px solid #444; border-radius: 4px; color: #d4d4d4; padding: 8px 12px; font: inherit; }
  input[type=text]:focus { outline: none; border-color: #264f78; }
  button[type=submit] { background: #264f78; color: #fff; border: none; border-radius: 4px; padding: 8px 16px; cursor: pointer; font: inherit; }
  button[type=submit]:disabled { opacity: 0.5; cursor: default; }
  #stop { background: #5a1d1d; color: #f48771; border: 1px solid #7a2d2d; border-radius: 4px; padding: 8px 16px; cursor: pointer; font: inherit; }
  #stop:hover { background: #6e2424; }
</style>
</head>
<body>
<header>
  <span class="title">local-agents</span>
  <span class="meta" id="meta">connecting...</span>
  <button id="new-session" type="button">New session</button>
</header>
<div id="log"></div>
<form id="composer">
  <input type="text" id="input" autocomplete="off" placeholder="Message..." autofocus>
  <button type="button" id="stop" hidden>Stop</button>
  <button type="submit" id="send">Send</button>
</form>
<script>
const log = document.getElementById('log');
const meta = document.getElementById('meta');
const input = document.getElementById('input');
const send = document.getElementById('send');
const form = document.getElementById('composer');
const newSession = document.getElementById('new-session');
const stop = document.getElementById('stop');
let after = 0;
let assistantBubble = null;

function setBusy(busy) {
  send.disabled = busy;
  stop.hidden = !busy;
}

function nearBottom() {
  return log.scrollHeight - log.scrollTop - log.clientHeight < 50;
}

function add(cls, text) {
  const stick = nearBottom();
  const div = document.createElement('div');
  div.className = cls;
  div.textContent = text;
  log.appendChild(div);
  if (stick) log.scrollTop = log.scrollHeight;
  return div;
}

function handleEvent(ev) {
  const p = ev.payload;
  switch (ev.kind) {
    case 'reply': {
      const stick = nearBottom();
      if (!assistantBubble) assistantBubble = add('msg assistant', '');
      assistantBubble.textContent += p;
      if (stick) log.scrollTop = log.scrollHeight;
      break;
    }
    case 'reply_done':
      assistantBubble = null;
      break;
    case 'tool_call': {
      const d = JSON.parse(p);
      add('event', '-> ' + d.name);
      break;
    }
    case 'tool_result': {
      const d = JSON.parse(p);
      if (d.error) add('event error', '<- ' + d.name + ' failed: ' + d.error);
      break;
    }
    case 'notice':
      add('event', '! ' + p);
      break;
    case 'approval_denied':
      add('event', '! approval denied for ' + p);
      break;
    case 'turn_failed':
      add('event error', 'The turn failed: ' + p);
      break;
    case 'turn_cancelled':
      add('event', p ? 'Interrupted: ' + p : 'Interrupted.');
      break;
    case 'error':
      add('event error', 'Error: ' + p);
      break;
    case 'session_ready':
      meta.textContent = meta.dataset.base + ' · ready';
      break;
    case 'turn_done':
      setBusy(false);
      input.focus();
      break;
  }
}

async function poll() {
  try {
    const res = await fetch('/api/events?after=' + after);
    const data = await res.json();
    for (const ev of data.events) {
      after = ev.id;
      handleEvent(ev);
    }
  } catch (e) {
    meta.textContent = 'connection lost';
  }
  setTimeout(poll, 500);
}

async function refreshSession() {
  const res = await fetch('/api/session');
  const data = await res.json();
  meta.dataset.base = data.agent + ' · session ' + (data.sdk_id || data.session_id);
  meta.textContent = meta.dataset.base;
}

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  add('msg user', text);
  input.value = '';
  setBusy(true);
  await fetch('/api/message', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({text}),
  });
});

stop.addEventListener('click', async () => {
  await fetch('/api/cancel', {method: 'POST'});
});

newSession.addEventListener('click', async () => {
  await fetch('/api/new', {method: 'POST'});
  log.innerHTML = '';
  after = 0;
  assistantBubble = null;
  setBusy(false);
  await refreshSession();
});

refreshSession().then(poll);
</script>
</body>
</html>
"""


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
            if parsed.path == "/":
                body = PAGE.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
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
                finally:
                    conn.close()
                self.send_json({
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
