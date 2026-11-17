import os
import re
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

BOT_ROOT = Path(__file__).resolve().parent / ".bots"
PROFILE_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")


def _load_profile() -> str:
    profile = os.environ.get("BOT_PROFILE", "default").strip() or "default"
    if not PROFILE_PATTERN.fullmatch(profile):
        raise ValueError(
            f"Invalid BOT_PROFILE {profile!r}: use letters, digits, '-' and '_', starting with a letter or digit."
        )
    return profile


PROFILE = _load_profile()
BOT_DIR = BOT_ROOT / PROFILE


@dataclass(frozen=True)
class AgentConfig:
    model: str
    context_window: int
    base_url: str
    api_key_env_var: str
    input_modalities: list[str] | None = None


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
    path = BOT_DIR / "config.toml"
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        raise ValueError(
            f"No configuration for profile {PROFILE!r}: {path} does not exist. "
            "Create it, or set BOT_PROFILE to an existing profile."
        ) from None


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
