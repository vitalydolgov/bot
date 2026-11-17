import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent / ".bot"


@dataclass(frozen=True)
class AgentConfig:
    model: str
    context_window: int
    base_url: str
    api_key_env_var: str


@dataclass(frozen=True)
class McpConfig:
    url: str
    auth_header_env_vars: dict[str, str] | None = None
    model_access: str | None = None
    disabled_tools: list[str] | None = None
    startup_timeout_seconds: float | None = None
    tool_timeout_seconds: float | None = None
    namespace: str | None = None
    id: str | None = None
    name: str | None = None


def _load_config() -> dict:
    with open(BOT_DIR / "config.toml", "rb") as f:
        return tomllib.load(f)


def _load_agent_config(data: dict) -> AgentConfig:
    return AgentConfig(**data["agent"])


def _load_mcp_configs(data: dict) -> dict[str, McpConfig]:
    known = {field.name for field in fields(McpConfig)}
    servers: dict[str, McpConfig] = {}
    for name, raw in data.get("mcp", {}).items():
        if not isinstance(raw, dict):
            raise ValueError(f"[mcp.{name}] must be a table")
        unknown = sorted(set(raw) - known)
        if unknown:
            raise ValueError(f"[mcp.{name}] has unknown keys: {', '.join(unknown)}")
        if "url" not in raw:
            raise ValueError(f"[mcp.{name}] is missing the required 'url' key")
        servers[name] = McpConfig(**raw)
    return servers


_DATA = _load_config()
CONFIG = _load_agent_config(_DATA)
MCP_SERVERS = {"chrome": McpConfig(url="http://127.0.0.1:8080/mcp"), **_load_mcp_configs(_DATA)}
