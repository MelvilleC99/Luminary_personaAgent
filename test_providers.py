#!/usr/bin/env python3
"""
Test different LLM providers to isolate the issue
"""

import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from tools.llm_tool import LLMTool

async def test_providers():
    """Test different LLM providers with the same prompt."""
    
    print("🔍 TESTING LLM PROVIDERS")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Setup API keys
    api_keys = {
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"), 
        "deepseek": os.getenv("DEEPSEEK_API_KEY")
    }
    
    # The actual Q2 prompt that's causing issues
    test_prompt = '''ASSESS Q2: "What's a niche within that topic where you have even more profound expertise?"

CRITERIA: Must be MORE SPECIFIC than Q1 answer. Look for processes, methods, specialized areas.

SCORE: 1-10 (7+ = advance, <7 = follow-up) 
FOLLOW-UP: "What specific aspect of your expertise do you focus on most?"

USER ANSWER: "I help them with planning their resources more effectively"

Respond JSON: {"score": X, "needs_follow_up": true/false, "follow_up_question": "...", "reasoning": "..."}'''
    
    print(f"📝 Test prompt length: {len(test_prompt)} characters")
    
    # Test each provider
    for provider_name in ["openai", "anthropic", "deepseek"]:
        if not api_keys.get(provider_name):
            print(f"⚠️ {provider_name.upper()}: No API key, skipping")
            continue
            
        print(f"\n🧪 Testing {provider_name.upper()}")
        print("-" * 30)
        
        try:
            llm_assignments = {"test_agent": provider_name}
            llm_tool = LLMTool(api_keys, llm_assignments)
            
            print(f"⏱️ Sending request to {provider_name}...")
            response = await llm_tool.generate_for_agent(
                "test_agent", 
                test_prompt, 
                session_id="test",
                temperature=0.1,
                max_tokens=200,
                timeout=20.0
            )
            
            print(f"✅ {provider_name.upper()} SUCCESS!")
            print(f"📝 Response: {response[:100]}...")
            
            # Try to parse as JSON
            import json
            try:
                parsed = json.loads(response)
                print(f"✅ JSON parsing: SUCCESS")
                print(f"📊 Score: {parsed.get('score', 'N/A')}")
            except:
                print(f"❌ JSON parsing: FAILED")
                
        except Exception as e:
            print(f"❌ {provider_name.upper()} FAILED: {e}")
            print(f"❌ Error type: {type(e).__name__}")

if __name__ == "__main__":
    asyncio.run(test_providers())
