#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI
import asyncio

load_dotenv()

async def debug_api():
    api_key = os.getenv("KIMI_API_KEY")
    base_url = os.getenv("KIMI_BASE_URL")
    
    print(f"API Key: {api_key[:10]}...{api_key[-4:]}")
    print(f"Key length: {len(api_key)}")
    print(f"Base URL: {base_url}")
    
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    try:
        response = await client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )
        print("✅ API Test Successful!")
        print(f"Response: {response.choices[0].message.content}")
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"Error type: {type(e)}")

if __name__ == "__main__":
    asyncio.run(debug_api())