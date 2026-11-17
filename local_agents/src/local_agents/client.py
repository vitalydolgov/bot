import json
import sqlite3
import time

from .store import (
    connect,
    create_session,
    delete_session,
    enqueue,
    find_session,
    get_agent,
    last_event_id,
    latest_session,
    read_events,
    session_sdk_id,
)

CLIENT_POLL_SECONDS = 0.2
TURN_TIMEOUT_SECONDS = 600


def print_event(event: sqlite3.Row) -> None:
    kind = event["kind"]
    payload = event["payload"]
    if kind == "reply":
        print(payload, end="", flush=True)
    elif kind == "reply_done":
        print()
    elif kind == "tool_call":
        data = json.loads(payload)
        print(f"-> {data['name']}")
    elif kind == "tool_result":
        data = json.loads(payload)
        print(f"<- {data['name']} {'failed: ' + data['error'] if data['error'] else 'done'}")
    elif kind == "notice":
        print(f"! {payload}")
    elif kind == "approval_denied":
        print(f"! approval denied for {payload} (the local worker cannot prompt)")
    elif kind == "turn_failed":
        print(f"The turn failed: {payload}")
    elif kind == "turn_cancelled":
        print(f"Interrupted: {payload}" if payload else "Interrupted.")
    elif kind == "error":
        print(f"Error: {payload}")


def stream_until(
    conn: sqlite3.Connection,
    session_id: str,
    stop_kinds: set[str],
    after_id: int = 0,
) -> tuple[int, str | None]:
    last_id = after_id
    deadline = time.monotonic() + TURN_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        events = read_events(conn, session_id, last_id)
        for event in events:
            last_id = event["id"]
            print_event(event)
            if event["kind"] in stop_kinds:
                return last_id, event["kind"]
        time.sleep(CLIENT_POLL_SECONDS)
    print("Timed out waiting for the agent.")
    return last_id, None


def delete(conn: sqlite3.Connection, ref: str) -> int:
    row = find_session(conn, ref)
    if row is None:
        print(f"No session {ref}.")
        return 1
    sdk_id = row["sdk_id"]
    if row["status"] == "ready":
        print(f"Warning: session {ref} is marked ready and may be open in another process.")
    delete_session(conn, row["id"])
    print(f"Deleted session {sdk_id or row['id']}.")
    return 0


def chat(agent_name: str, message: str | None, new: bool, resume_ref: str | None, delete_ref: str | None) -> int:
    conn = connect()
    if delete_ref is not None:
        return delete(conn, delete_ref)
    if get_agent(conn, agent_name) is None:
        print(f"No agent named {agent_name}. Start it with `uv run local-agents serve`.")
        return 1
    resumed = False
    if resume_ref is not None:
        row = find_session(conn, resume_ref)
        if row is None:
            print(f"No session {resume_ref}.")
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
    cursor, stopped = stream_until(conn, session_id, {"session_ready", "error"}, last_event_id(conn, session_id))
    if stopped == "error":
        return 1
    try:
        if message is not None:
            enqueue(conn, session_id, "message", {"text": message})
            stream_until(conn, session_id, {"turn_done", "error"}, cursor)
            return 0
        shown = session_sdk_id(conn, session_id) or session_id
        where = f"Resuming session {shown}" if resumed else f"Talking to {agent_name} (session {shown})"
        print(f"{where}. Ctrl+D or /exit to quit.")
        while True:
            try:
                text = input("> ")
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if text.strip() in ("/exit", "/quit"):
                return 0
            if not text.strip():
                continue
            enqueue(conn, session_id, "message", {"text": text})
            cursor, _ = stream_until(conn, session_id, {"turn_done", "error"}, cursor)
    finally:
        enqueue(conn, session_id, "detach", {})
