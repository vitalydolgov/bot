# Bot

A framework for creating specialized bots built on the Mistral Agents SDK. It provides a shared foundation for defining, configuring, and running purpose-built agents, so each bot can focus on its own domain and behavior.

## Features

- Persistent memory — the agent remembers things across turns and sessions.
- Skills — the agent can use skills and author its own, so it can learn new procedures over time.
- MCP — the agent can call tools on remote MCP servers.
- Chrome — the agent can drive a headless desktop Chrome browser through Chrome DevTools.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — installs the dependencies and runs the bot.
- Python 3.12+ on the login-shell PATH. Check with `bash -lc 'python3 --version'`; if it reports an older version, prepend a newer Python to PATH in `~/.bash_profile`.
- [Chrome](https://www.google.com/chrome/) — required for the chrome skill.
- [Node.js](https://nodejs.org/) — provides `npx`, required for the chrome skill's MCP bridge.

## Setup

From the project root:

```sh
uv sync
```

This creates a virtual environment in `.venv` and installs the project dependencies.

## Profiles

Each bot runs as a profile with its own configuration and memory, stored under `.bots/<profile>/`. The workspace and skills are shared by all profiles and stored under `.bots/workspace/`. The `default` profile is used when nothing else is selected; pick another with the `BOT_PROFILE` environment variable, either per command or in `.env`:

```sh
BOT_PROFILE=anotherbot uv run agents chat
```

A profile directory holds `config.toml` and `MEMORY.md`. The agent's registered name is the profile name. To create a profile, make `.bots/<name>/` with a `config.toml`; the rest is created on first use. The shared workspace lives in `.bots/workspace/`; skills live in `.bots/workspace/.agents/skills/`, seeded from the built-in skills on first use.

## Configuration

Configuration has two levels:

- Common — `.bots/config.toml`, common to all profiles. Holds the default model endpoint and MCP servers shared by every bot.
- Profile — `.bots/<profile>/config.toml`, where `<profile>` is the `BOT_PROFILE` environment variable (`default` when unset). Holds the model endpoint (replacing the common one entirely) and any profile-specific MCP servers; a profile MCP server with the same name as a common one replaces it.

See [docs/config.md](docs/config.md) for the full format.

### Environment

Set these in a `.env` file in the project root (or in the environment). Variables already set in the environment take precedence over `.env`; the file only fills in what is missing.

- `MISTRAL_API_KEY` — authenticates with Mistral, needed to serve the agent and to talk to it through the Session API.
- `ALLOW_DANGEROUS_LOCAL_HOST` — set to `1` to let the agent run commands directly on your machine.
- Any variables referenced by `auth_header_env_vars` of the MCP servers in `.bots/config.toml` or `.bots/<profile>/config.toml`.

## Run

Two modes, depending on where the agent runs:

Local — the agent runs in this process, nothing is registered with Mistral, and only the model endpoint key is needed:

```sh
uv run agents chat
```

Set `BOT_PROFILE` to run a different profile (see Profiles).

Remote — the agent is registered in your Mistral workspace and runs on your machine as a worker, giving you a hosted chat link. It sends the agent's configuration to Mistral (pass `--no-send-config` to skip that) and polls Mistral's task queue over an outbound connection, so no inbound ports are opened. Stop it with Ctrl+C; the agent stays registered but receives no sessions until you serve it again:

```sh
uv run agents serve
```

## Smoke test

```sh
uv run smoke.py
```

Runs a single turn against the model endpoint and prints the reply.

