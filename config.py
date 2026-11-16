import tomllib
from dataclasses import dataclass
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent / ".bot"


@dataclass(frozen=True)
class AgentConfig:
    model: str
    context_window: int
    base_url: str
    api_key_env_var: str


def _load_agent_config() -> AgentConfig:
    with open(BOT_DIR / "config.toml", "rb") as f:
        data = tomllib.load(f)
    return AgentConfig(**data["agent"])


CONFIG = _load_agent_config()
