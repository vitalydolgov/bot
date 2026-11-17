import asyncio
import contextlib
import json
import sqlite3
from pathlib import Path

from .store import (
    DB_PATH,
    JOURNAL_DIR,
    append_event,
    claim_command,
    connect,
    finish_command,
    register_agent,
    set_session_status,
)

POLL_SECONDS = 0.5


class StoreOutput:
    def __init__(self, conn: sqlite3.Connection, session_id: str) -> None:
        self._conn = conn
        self._session_id = session_id

    def _emit(self, kind: str, payload: str) -> None:
        append_event(self._conn, self._session_id, kind, payload)

    def reply(self, text: str) -> None:
        self._emit("reply", text)

    def reply_done(self) -> None:
        self._emit("reply_done", "")

    def tool_call(self, name: str, arguments: object) -> None:
        self._emit("tool_call", json.dumps({"name": name, "arguments": arguments}))

    def tool_result(self, name: str, error: str | None) -> None:
        self._emit("tool_result", json.dumps({"name": name, "error": error}))

    def ask_approval(self, callback: object) -> object:
        from mistralai.vibe_agents.sdk.app.chat import ApprovalAnswer

        name = getattr(callback, "name", None) or getattr(callback, "tool_id", None) or "approval"
        self._emit("approval_denied", str(name))
        return ApprovalAnswer.DENY

    def notice(self, message: str) -> None:
        self._emit("notice", message)

    def turn_failed(self, message: str) -> None:
        self._emit("turn_failed", message)

    def turn_cancelled(self, reason: str | None) -> None:
        self._emit("turn_cancelled", reason or "")


async def _ensure_client(
    conn: sqlite3.Connection,
    loaded: object,
    sessions: dict[str, object],
    session_id: str,
) -> object:
    client = sessions.get(session_id)
    if client is not None:
        return client
    row = conn.execute("SELECT sdk_id FROM sessions WHERE id = ?", (session_id,)).fetchone()
    sdk_id = row["sdk_id"] if row else None
    if not sdk_id:
        raise RuntimeError("this session predates resume support; start a new one with --new")
    from mistralai.vibe_agents.sdk.transport import local as local_transport

    runtime = local_transport._running_process_runtime()
    if runtime is None:
        raise RuntimeError("the local runtime is not running")
    client = await runtime.get_session(
        sdk_id,
        reassemble=lambda: loaded.agent._reassemble_local_root(runtime, sdk_id),
    )
    sessions[session_id] = client
    return client


async def handle_command(
    conn: sqlite3.Connection,
    loaded: object,
    sessions: dict[str, object],
    command: sqlite3.Row,
) -> None:
    from mistralai.vibe_agents.sdk.app import chat

    session_id = command["session_id"]
    payload = json.loads(command["payload"])
    try:
        if command["kind"] == "start":
            client = await loaded.agent._create_session()
            sessions[session_id] = client
            conn.execute(
                "UPDATE sessions SET sdk_id = ?, status = 'ready' WHERE id = ?",
                (client.session_id, session_id),
            )
            append_event(conn, session_id, "session_ready", client.session_id)
        elif command["kind"] == "resume":
            client = await _ensure_client(conn, loaded, sessions, session_id)
            set_session_status(conn, session_id, "ready")
            append_event(conn, session_id, "session_ready", client.session_id)
        elif command["kind"] == "message":
            client = await _ensure_client(conn, loaded, sessions, session_id)
            output = StoreOutput(conn, session_id)
            completed = await chat.run_turn(client, payload["text"], output)
            append_event(conn, session_id, "turn_done", "completed" if completed else "failed")
        elif command["kind"] == "detach":
            client = sessions.pop(session_id, None)
            if client is not None:
                await client.close()
            set_session_status(conn, session_id, "idle")
            append_event(conn, session_id, "session_detached", "")
        else:
            raise RuntimeError(f"unknown command kind {command['kind']!r}")
        finish_command(conn, command["id"], "done")
    except Exception as exc:
        append_event(conn, session_id, "error", str(exc))
        finish_command(conn, command["id"], "failed")


async def serve(project: Path, name: str | None) -> None:
    from mistralai import agents
    from mistralai.agents import experimental
    from mistralai.vibe_agents.sdk.app import loader

    loaded = loader.load_app(project)
    agent_name = name or loaded.name
    conn = connect()
    register_agent(conn, agent_name, project.resolve())
    sessions: dict[str, object] = {}
    print(f"Serving {agent_name} from {project.resolve()}", flush=True)
    print(f"Polling {DB_PATH} for commands. Ctrl+C to stop.", flush=True)
    try:
        async with agents.local_runtime(
            journal_factory=experimental.JsonFileSessionJournal.in_directory(JOURNAL_DIR)
        ):
            while True:
                command = claim_command(conn)
                if command is None:
                    await asyncio.sleep(POLL_SECONDS)
                    continue
                await handle_command(conn, loaded, sessions, command)
    finally:
        for client in sessions.values():
            with contextlib.suppress(Exception):
                await client.close()
