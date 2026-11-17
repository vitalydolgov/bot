import asyncio
import contextlib
import json
import os
import re
import sqlite3
import sys
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
PROFILE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def discover_profiles(project: Path) -> list[str | None]:
    bots = project / ".bots"
    profiles: list[str | None] = []
    if (bots / "config.toml").is_file():
        profiles.append(None)
    profiles_dir = bots / "profiles"
    if profiles_dir.is_dir():
        for child in sorted(profiles_dir.iterdir()):
            if not child.is_dir() or not (child / "config.toml").is_file():
                continue
            if not PROFILE_PATTERN.fullmatch(child.name):
                print(f"Skipping {child.name}: not a valid profile name", flush=True)
                continue
            profiles.append(child.name)
    return profiles


def _purge_project_modules(project: Path) -> None:
    root = str(project.resolve()) + os.sep
    own = str(Path(__file__).resolve().parent) + os.sep
    for name, module in list(sys.modules.items()):
        file = getattr(module, "__file__", None)
        if file is None:
            continue
        resolved = str(Path(file).resolve())
        if not resolved.startswith(root) or resolved.startswith(own):
            continue
        if "site-packages" in resolved or "dist-packages" in resolved:
            continue
        del sys.modules[name]


def _load_profile(project: Path, profile: str | None) -> object:
    if profile is None:
        os.environ.pop("BOT_PROFILE", None)
    else:
        os.environ["BOT_PROFILE"] = profile
    _purge_project_modules(project)
    from mistralai.vibe_agents.sdk.app import loader

    return loader.load_app(project)


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


def _session_agent(conn: sqlite3.Connection, session_id: str) -> str | None:
    row = conn.execute("SELECT agent FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return row["agent"] if row else None


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
    loaded_by_agent: dict[str, object],
    sessions: dict[str, object],
    command: sqlite3.Row,
) -> None:
    from mistralai.vibe_agents.sdk.app import chat

    session_id = command["session_id"]
    payload = json.loads(command["payload"])
    agent_name = _session_agent(conn, session_id)
    loaded = loaded_by_agent.get(agent_name or "")
    try:
        if loaded is None:
            raise RuntimeError(f"agent {agent_name!r} is not being served")
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
            try:
                client = await _ensure_client(conn, loaded, sessions, session_id)
                output = StoreOutput(conn, session_id)
                completed = await chat.run_turn(client, payload["text"], output)
            except asyncio.CancelledError:
                append_event(conn, session_id, "turn_cancelled", "")
                append_event(conn, session_id, "turn_done", "cancelled")
                finish_command(conn, command["id"], "done")
                raise
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


async def serve(project: Path, profile: str | None) -> None:
    from mistralai import agents
    from mistralai.agents import experimental

    env_profile = os.environ.get("BOT_PROFILE", "").strip() or None
    if profile is not None:
        selected = [profile]
    elif env_profile is not None:
        selected = [env_profile]
    else:
        selected = discover_profiles(project)
        if not selected:
            raise SystemExit(
                f"No profiles found in {project / '.bots'}: "
                "add a config.toml to .bots/ or .bots/profiles/<profile>/"
            )

    original_profile = os.environ.get("BOT_PROFILE")
    loaded_by_agent: dict[str, object] = {}
    conn = connect()
    try:
        for prof in selected:
            try:
                loaded = _load_profile(project, prof)
            except Exception as exc:
                print(f"Skipping {prof or 'bot'}: {exc}", flush=True)
                continue
            agent_name = loaded.name
            if agent_name in loaded_by_agent:
                print(f"Skipping {prof or 'bot'}: agent name {agent_name!r} is already served", flush=True)
                continue
            register_agent(conn, agent_name, project.resolve())
            loaded_by_agent[agent_name] = loaded
            print(f"Serving {agent_name} from {project.resolve()}", flush=True)
    finally:
        if original_profile is None:
            os.environ.pop("BOT_PROFILE", None)
        else:
            os.environ["BOT_PROFILE"] = original_profile
    if not loaded_by_agent:
        raise SystemExit("No agents could be loaded.")

    sessions: dict[str, object] = {}
    turn_task: asyncio.Task | None = None
    turn_session_id: str | None = None
    print(f"Polling {DB_PATH} for commands. Ctrl+C to stop.", flush=True)
    try:
        async with agents.local_runtime(
            journal_factory=experimental.JsonFileSessionJournal.in_directory(JOURNAL_DIR)
        ):
            while True:
                if turn_task is not None and turn_task.done():
                    if not turn_task.cancelled() and (exc := turn_task.exception()) is not None:
                        print(f"Turn failed: {exc}", flush=True)
                    turn_task = None
                    turn_session_id = None
                busy = turn_task is not None
                command = claim_command(conn, list(loaded_by_agent), only_kinds=["cancel"] if busy else None)
                if command is None:
                    await asyncio.sleep(POLL_SECONDS)
                    continue
                if command["kind"] == "cancel":
                    if busy and command["session_id"] == turn_session_id:
                        turn_task.cancel()
                        try:
                            await turn_task
                        except asyncio.CancelledError:
                            pass
                        turn_task = None
                        turn_session_id = None
                    else:
                        append_event(conn, command["session_id"], "notice", "No turn is running.")
                    finish_command(conn, command["id"], "done")
                    continue
                if command["kind"] == "message":
                    turn_session_id = command["session_id"]
                    turn_task = asyncio.create_task(handle_command(conn, loaded_by_agent, sessions, command))
                    continue
                await handle_command(conn, loaded_by_agent, sessions, command)
    finally:
        if turn_task is not None and not turn_task.done():
            turn_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await turn_task
        for client in sessions.values():
            with contextlib.suppress(Exception):
                await client.close()
