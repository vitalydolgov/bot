# Configuration

The bot reads its configuration from `.bot/config.toml` at startup. The file has two kinds of tables: one `[agent]` table for the model endpoint, and one `[mcp.<name>]` table per MCP server.

## `[agent]`

Required. Configures the model the agent calls.

| Key | Type | Description |
| --- | --- | --- |
| `model` | string | The model identifier, passed to the completion endpoint. |
| `context_window` | integer | The model's context window in tokens. Used to size automatic compaction of older turns. |
| `base_url` | string | The base URL of an OpenAI-compatible completions API. |
| `api_key_env_var` | string | Name of the environment variable holding the API key for that endpoint. The variable is read from the environment (or `.env`), never from this file. |

Example:

```toml
[agent]
model = "nvidia/nemotron-3.5-lightning-30b-a3b"
context_window = 262144
base_url = "https://integrate.api.nvidia.com/v1"
api_key_env_var = "NVIDIA_API_KEY"
```

## `[mcp.<name>]`

Optional, repeatable. Declares a remote MCP server the agent can call tools on. Only HTTP(S) servers are supported. The `<name>` you choose becomes the namespace of the server's tools — a tool `create_issue` on `[mcp.github]` is exposed to the model as `github.create_issue` — and also defaults the server's ID and display name. Two servers may not share a namespace.

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

