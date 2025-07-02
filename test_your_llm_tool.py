#!/usr/bin/env python3
"""
Test your exact LLM tool to see where the difference is
"""

import asyncio
import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from tools.llm_tool import LLMTool

async def test_your_llm_tool():
    """Test your exact LLM tool setup."""
    
    print("🔍 TESTING YOUR LLM TOOL SETUP")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Setup exactly like your application
    api_keys = {
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY")
    }
    
    llm_assignments = {
        "question_agent": "openai"
    }
    
    llm_tool = LLMTool(api_keys, llm_assignments)
    
    # Test the exact same prompt and parameters
    test_prompt = '''ASSESS Q2: "What's a niche within that topic where you have even more profound expertise?"

CRITERIA: Must be MORE SPECIFIC than Q1 answer. Look for processes, methods, specialized areas.

SCORE: 1-10 (7+ = advance, <7 = follow-up) 
FOLLOW-UP: "What specific aspect of your expertise do you focus on most?"

USER ANSWER: "I help them with planning their resources more effectively"

Respond with ONLY valid JSON (no markdown):
{"score": X, "needs_follow_up": true/false, "follow_up_question": "...", "reasoning": "..."}'''
    
    print(f"📝 Testing with prompt length: {len(test_prompt)}")
    
    try:
        print("⏱️ Starting request through your LLM tool...")
        start_time = time.time()
        
        response = await llm_tool.generate_for_agent(
            "question_agent",
            test_prompt,
            session_id="test_session",
            temperature=0.1,
            max_tokens=150,
            timeout=15.0
        )
        
        elapsed = time.time() - start_time
        print(f"✅ SUCCESS in {elapsed:.2f}s")
        print(f"📝 Response: {response}")
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ FAILED after {elapsed:.2f}s: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        
        # Let's also check the provider assignment
        print(f"\n🔍 Debug info:")
        print(f"Provider for question_agent: {llm_tool.get_agent_assignment('question_agent')}")
        print(f"Available providers: {llm_tool.get_available_providers()}")

if __name__ == "__main__":
    asyncio.run(test_your_llm_tool())
