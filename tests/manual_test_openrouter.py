#!/usr/bin/env python
"""Test script for OpenRouter provider integration."""

import asyncio
import os
from aishell.llm import OpenRouterLLMProvider
from aishell.utils import load_env_on_startup

async def test_openrouter():
    """Test OpenRouter provider functionality."""
    # Load environment variables
    load_env_on_startup()
    
    # Check if API key is configured
    api_key = os.environ.get('OPENROUTER_API_KEY')
    if not api_key:
        print("❌ OPENROUTER_API_KEY not found in environment")
        print("Please add it to your .env file:")
        print("OPENROUTER_API_KEY=your-openrouter-api-key-here")
        return
    
    print("✅ OpenRouter API key found")
    
    # Create provider
    provider = OpenRouterLLMProvider()
    
    # Validate configuration
    if provider.validate_config():
        print("✅ Provider configuration valid")
    else:
        print("❌ Provider configuration invalid")
        return
    
    print(f"📍 Using endpoint: {provider.base_url}")
    print(f"🤖 Default model: {provider.default_model}")
    
    # Test query
    print("\n🔄 Testing query...")
    response = await provider.query("Hello! Please respond with a simple greeting.")
    
    if response.is_error:
        print(f"❌ Query failed: {response.error}")
    else:
        print(f"✅ Query successful!")
        print(f"Model: {response.model}")
        print(f"Response: {response.content[:100]}...")
        if response.usage:
            print(f"Tokens: {response.usage}")
        if response.metadata:
            print(f"Metadata: {response.metadata}")
    
    # Test streaming
    print("\n🔄 Testing streaming...")
    try:
        print("Stream response: ", end="", flush=True)
        async for chunk in provider.stream_query("Count from 1 to 5"):
            print(chunk, end="", flush=True)
        print("\n✅ Streaming successful!")
    except Exception as e:
        print(f"\n❌ Streaming failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_openrouter())