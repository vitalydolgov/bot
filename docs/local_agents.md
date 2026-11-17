# Local agents

`local-agents` is a local stand-in for `agents serve` and `agents chat`. The hosted commands register the agent with Mistral's control plane and poll its task queue; sessions and their events live on the service. `local-agents` keeps the same shape without the service: a local store holds the agent registry, the sessions, a command queue and an event log, and a worker polls it. Nothing is registered with Mistral and the Session API is not used, so only the model endpoint key from `.bots/config.toml` is needed.

## Commands

```sh
uv run local-agents serve                  # register every profile found in .bots/profiles/ and poll for work
uv run local-agents serve --profile grad   # serve only grad
uv run local-agents chat                   # resume the latest session (or start one)
uv run local-agents chat --new             # start a fresh session
uv run local-agents webui                  # serve a web client at http://127.0.0.1:8000/
```

### `serve`

Discovers the profiles to serve and loads each from `./main.py` (override with `--path`):

- The common config `.bots/config.toml`, served as `bot`.
- Every `.bots/profiles/<profile>/config.toml`, served as `<profile>`.

Each profile gets its own configuration and memory. A profile that fails to load is skipped with an error; the rest are served. Stop it with Ctrl+C. The agents stay registered but receive no sessions until you serve them again.

- `--profile <name>` serves only that profile.
- `BOT_PROFILE` set in the environment serves only that profile.

Profiles never run each other's sessions.

### `chat`

Talks to a served agent. The agent argument is optional and defaults to `bot`.

| Flag | Description |
| --- | --- |
| `-m`, `--message` | Send a single message and exit. Without it, an interactive prompt opens; Ctrl+D or `/exit` quits. |
| `--new` | Start a fresh session instead of resuming. |
| `--resume` | Resume a specific session, by either of its ids (see below). |
| `--delete` | Delete a session, by either of its ids, and exit. Removes its rows from the store. |

Exiting the chat detaches from the session; it stays resumable. By default `chat` resumes the most recent session for the agent that has been started at least once.

### `webui`

Serves a web client for a served agent at `http://127.0.0.1:8000/`. The agent argument is optional and defaults to `bot`.

| Flag | Description |
| --- | --- |
| `--port` | Port to listen on. Defaults to 8000. |
| `--new` | Start a fresh session instead of resuming. |
| `--resume` | Resume a specific session, by either of its ids (see below). |

The page mirrors the chat: it resumes the latest session (or starts one), streams the event log into the browser, and sends messages through the same command queue. A "New session" button detaches from the current session and starts a fresh one. While a turn is running, a "Stop" button interrupts it. Stopping the server with Ctrl+C detaches from the session; it stays resumable.

## How it works

The worker and the clients never talk to each other directly. They communicate through the store:

- The clients enqueue commands and poll the event log.
- The worker polls the command queue, claims one command at a time, runs the turn in-process, and appends events to the log.
- A message sent while a turn is running stays queued and runs after it; the running turn can be interrupted, which leaves the session usable.

Sessions are journaled to disk, so they survive worker restarts and can be resumed in a later process.

Each session has two ids; `--resume` and `--delete` accept either.

## State

All state lives under `.bots/`:

- `.bots/local_serve.db` — the store.
- `.bots/sessions/` — session journals.

Deleting both resets all local state.

