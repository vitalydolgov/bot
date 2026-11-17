# Configuration

The bot reads its configuration from two files at startup:

1. `~/.bots/config.toml` — the common config, shared by all profiles.
2. `~/.bots/profiles/<profile>/config.toml` — the profile config, where `<profile>` is the `BOT_PROFILE` environment variable (it may also be set in `.env`). Read only when `BOT_PROFILE` is set; otherwise only the common config is read.

A profile table replaces the common table of the same name entirely.

## Schema

Both files use the same format. A config file may contain these top-level tables and nothing else:

- `[agent]` — the model endpoint; see below.
- `[mcp.<name>]` — a remote MCP server the agent can call tools on; repeatable, see below.

The common file may be absent; the profile file is read only when `BOT_PROFILE` is set. The model endpoint must be configured in at least one of the files that are read.

## `[agent]`

Configures the model the agent calls. It can be set in either file; the common `[agent]` provides defaults for every bot, and a profile `[agent]` replaces it entirely.

| Key | Type | Description |
| --- | --- | --- |
| `model` | string | The model identifier, passed to the completion endpoint. |
| `context_window` | integer | The model's context window in tokens. Used to size automatic compaction of older turns. |
| `base_url` | string | The base URL of an OpenAI-compatible completions API. |
| `api_key_env_var` | string | Name of the environment variable holding the API key for that endpoint. The variable is read from the environment (or `.env`), never from this file. |
| `input_modalities` | list of strings | The input modalities the model accepts, e.g. `["text", "image"]`. When unset, the bot detects them automatically. |

Example:

```toml
[agent]
model = "nvidia/nemotron-3.5-lightning-30b-a3b"
context_window = 262144
base_url = "https://integrate.api.nvidia.com/v1"
api_key_env_var = "NVIDIA_API_KEY"
```

## `[mcp.<name>]`

Repeatable, in either config file. Declares a remote MCP server the agent can call tools on. Only HTTP(S) servers are supported. The `<name>` you choose becomes the namespace of the server's tools — a tool `create_issue` on `[mcp.github]` is exposed to the model as `github.create_issue` — and also defaults the server's ID and display name. Two servers may not share a namespace.

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `url` | string | required | The server's `http://` or `https://` endpoint. Anything else is rejected at startup. |
| `auth_header_env_vars` | table | none | Headers to send with every request, mapping header name to the name of the environment variable holding the header's full value. See below. |
| `model_access` | string | `"direct"` without programs, `"programmatic"` otherwise | How the model reaches the server's tools: `"direct"`, `"programmatic"` or `"both"`. |
| `disabled_tools` | list of strings | none | The server's own tool names to leave out. |
| `startup_timeout_seconds` | float | `30` | How long listing the server's tools may take. |
| `tool_timeout_seconds` | float | `300` | How long one tool call may take. |
| `namespace` | string | `<name>` | Overrides the namespace of the server's tools. |
| `id` | string | `<name>` | Overrides the server's ID, reported as the source of its tools and messages. |
| `name` | string | `<name>` | Overrides the server's display name, used in messages the model gets about it. |

### `auth_header_env_vars`

Maps each header name to the **name of an environment variable**, not to the secret itself. The variable is read where the agent runs — locally for `agents chat`, on the worker for `agents serve` — and its value is sent verbatim as the header.

```toml
[mcp.github]
url = "https://api.githubcopilot.com/mcp/"
auth_header_env_vars = { Authorization = "GITHUB_MCP_TOKEN" }
```

With `GITHUB_MCP_TOKEN=Bearer ghp_...` in `.env`, every request to the server carries `Authorization: Bearer ghp_...`. Keep the secret in `.env` (or the environment), never in `config.toml`. If a referenced variable is unset or blank, the server's credentials are reported as missing rather than sent empty.

## Built-in `chrome` server

The bot ships with a built-in `chrome` MCP server pointing at `http://127.0.0.1:8080/mcp`, so no declaration is needed for the default endpoint. To use a different endpoint, declare `[mcp.chrome]` with your own `url` in either config file; it replaces the built-in default. All other `[mcp.chrome]` keys are honored as usual.

```toml
[mcp.chrome]
url = "http://127.0.0.1:9999/mcp"
```
