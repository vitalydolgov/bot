# Bot

A framework for creating specialized bots built on the Mistral Agents SDK. It provides a shared foundation for defining, configuring, and running purpose-built agents, so each bot can focus on its own domain and behavior.

## Features

- Persistent memory — the agent keeps durable notes in `.bot/MEMORY.md`, so it remembers things across turns and sessions.
- Skills — the agent can use skills and author its own, so it can learn new procedures over time.

## Setup

Requires [uv](https://docs.astral.sh/uv/). From the project root:

```sh
uv sync
```

This creates a virtual environment in `.venv` and installs the project dependencies.

A `python3` ≥ 3.12 must be on the login-shell PATH. Check with `bash -lc 'python3 --version'`; if it reports an older version, prepend a newer Python to PATH in `~/.bash_profile`.

Set these in a `.env` file in the project root (or in the environment):

- `NVIDIA_API_KEY` — authenticates the model endpoint the agent calls.
- `MISTRAL_API_KEY` — authenticates with Mistral, needed to serve the agent and to talk to it through the Session API.
- `ALLOW_DANGEROUS_LOCAL_HOST` — set to `1` to let the agent run commands directly on your machine.

## Run

Two modes, depending on where the agent runs:

Local — the agent runs in this process, nothing is registered with Mistral, and only `NVIDIA_API_KEY` is needed:

```sh
uv run agents chat
```

Remote — the agent is registered in your Mistral workspace and runs on your machine as a worker, giving you a hosted chat link. It sends the agent's configuration to Mistral (pass `--no-send-config` to skip that) and polls Mistral's task queue over an outbound connection, so no inbound ports are opened. Stop it with Ctrl+C; the agent stays registered but receives no sessions until you serve it again:

```sh
uv run agents serve
```

## Smoke test

```sh
uv run smoke.py
```

Runs a single turn against the model endpoint and prints the reply.

