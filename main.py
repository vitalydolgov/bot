from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from config import CONFIG, PROFILE, WORKSPACE_DIR
from mcp_servers import load_mcps
from modalities import detect_input_modalities
from tools.memory import MEMORY_TOOLS, memory_instructions
from patches.mistralai import apply_sdk_patches
from tools.read_image import READ_IMAGE_TOOLS
from mistralai import agents
from mistralai.vibe.harness.runtime.completion.providers.openai import OpenAICompletionConfig
from skills import seed_skills

seed_skills()

apply_sdk_patches()

PROMPTS_DIR = Path(__file__).resolve().parent / "instructions" / "prompts"
MODALITY_PROMPTS = {"image": PROMPTS_DIR / "vision.md"}


def modality_instructions(modalities: list[str]) -> str:
    parts = []
    for modality in modalities:
        path = MODALITY_PROMPTS.get(modality)
        if path is not None:
            parts.append(path.read_text(encoding="utf-8").strip())
    return "\n\n".join(parts)


modalities = CONFIG.input_modalities or detect_input_modalities(CONFIG.base_url, CONFIG.model, CONFIG.api_key_env_var)
instructions = "\n\n".join(part for part in (modality_instructions(modalities), memory_instructions()) if part)

agent = agents.Agent(
    name=PROFILE or "bot",
    model=CONFIG.model,
    instructions=instructions,
    tools=[*MEMORY_TOOLS, *READ_IMAGE_TOOLS],
    environment=agents.DangerousLocalSandbox(workspace=str(WORKSPACE_DIR)),
    skills=[agents.SandboxWorkspaceSkills()],
    mcps=load_mcps() or None,
    completion=OpenAICompletionConfig(
        model=CONFIG.model,
        api_key_env_var=CONFIG.api_key_env_var,
        base_url=CONFIG.base_url,
        context_window=CONFIG.context_window,
        input_modalities=modalities,
    ),
)
