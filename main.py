from dotenv import load_dotenv

load_dotenv()

from config import BOT_DIR, CONFIG
from mistralai import agents
from mistralai.vibe.harness.runtime.completion.providers.openai import OpenAICompletionConfig

agent = agents.Agent(
    name="bot",
    model=CONFIG.model,
    instructions="You are a concise assistant.",
    completion=OpenAICompletionConfig(
        model=CONFIG.model,
        api_key_env_var=CONFIG.api_key_env_var,
        base_url=CONFIG.base_url,
        context_window=CONFIG.context_window,
    ),
)
