from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config import CONFIG
from memory import MEMORY_TOOLS, memory_instructions
from mistralai import agents
from mistralai.vibe.harness.runtime.completion.providers.openai import OpenAICompletionConfig

INTRO_PATH = Path(__file__).resolve().parent / "prompts" / "intro.md"
intro = INTRO_PATH.read_text(encoding="utf-8").strip()

agent = agents.Agent(
    name="bot",
    model=CONFIG.model,
    instructions=f"{intro}\n\n{memory_instructions()}",
    tools=MEMORY_TOOLS,
    completion=OpenAICompletionConfig(
        model=CONFIG.model,
        api_key_env_var=CONFIG.api_key_env_var,
        base_url=CONFIG.base_url,
        context_window=CONFIG.context_window,
    ),
)
