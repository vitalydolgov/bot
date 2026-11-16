# Bot

A framework for creating specialized bots built on the Mistral Agents SDK. It provides a shared foundation for defining, configuring, and running purpose-built agents, so each bot can focus on its own domain and behavior.

## Setup

Requires [uv](https://docs.astral.sh/uv/). From the project root:

```sh
uv sync
```

This creates a virtual environment in `.venv` and installs the project dependencies.

Set two keys in a `.env` file in the project root (or in the environment):

- `NVIDIA_API_KEY` — authenticates the model endpoint the agent calls.
- `MISTRAL_API_KEY` — authenticates with Mistral, needed to serve the agent and to talk to it through the Session API.

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

## Memory

The agent keeps durable notes in `.bot/MEMORY.md`. The file is read into its instructions at startup, and the agent can update it with its memory tools, so it remembers things across turns and sessions. The instructions themselves live in `prompts/memory.md`; `{memory_contents}` is filled in at startup.

## Smoke test

```sh
uv run smoke.py
```

Runs a single turn against the model endpoint and prints the reply.

