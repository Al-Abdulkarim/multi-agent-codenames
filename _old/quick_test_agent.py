import asyncio
import os
from config import GameConfig
from agents.content_agent import ContentCreationAgent
from dotenv import load_dotenv

load_dotenv()


async def test_agent():
    config = GameConfig()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("Error: GOOGLE_API_KEY not found in .env")
        return

    config.google_api_key = api_key
    agent = ContentCreationAgent(config)

    print("Testing word generation...")
    try:
        words = await agent.generate_word_list(25)
        print(f"Success! Generated words: {words}")
    except Exception as e:
        print(f"Failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_agent())
