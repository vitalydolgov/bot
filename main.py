import asyncio

from dotenv import load_dotenv

load_dotenv()

from mistralai import agents
from mistralai.vibe.harness.runtime.completion.providers.openai import OpenAICompletionConfig

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

agent = agents.Agent(
    model="nvidia/nemotron-3.5-lightning-30b-a3b",
    instructions="You are a concise assistant.",
    completion=OpenAICompletionConfig(
        model="nvidia/nemotron-3.5-lightning-30b-a3b",
        api_key_env_var="NVIDIA_API_KEY",
        base_url=NVIDIA_BASE_URL,
        context_window=262144,
    ),
)


async def main() -> None:
    result = await agent.run("Reply with exactly: pong")
    print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
