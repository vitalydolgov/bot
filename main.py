from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config import BOT_DIR, CONFIG
from mcp_servers import load_mcps
from memory import MEMORY_TOOLS, memory_instructions
from mistralai import agents
from mistralai.vibe.harness.runtime.completion.providers.openai import OpenAICompletionConfig
from skills import load_skills

INTRO_PATH = Path(__file__).resolve().parent / "instructions" / "prompts" / "intro.md"
intro = INTRO_PATH.read_text(encoding="utf-8").strip()

agent = agents.Agent(
    name="bot",
    model=CONFIG.model,
    instructions=f"{intro}\n\n{memory_instructions()}",
    tools=MEMORY_TOOLS,
    environment=agents.DangerousLocalSandbox(workspace=str(BOT_DIR / "workspace")),
    skills=[*load_skills(), agents.SandboxWorkspaceSkills()],
    mcps=load_mcps() or None,
    completion=OpenAICompletionConfig(
        model=CONFIG.model,
        api_key_env_var=CONFIG.api_key_env_var,
        base_url=CONFIG.base_url,
        context_window=CONFIG.context_window,
    ),
)
