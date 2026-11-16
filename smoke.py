import asyncio

from dotenv import load_dotenv

load_dotenv()

from main import agent


async def main() -> None:
    result = await agent.run("Reply with exactly: pong")
    print(result.text)


if __name__ == "__main__":
    asyncio.run(main())
