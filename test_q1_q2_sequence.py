#!/usr/bin/env python3
"""
Test to isolate Q2 specific issue
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

async def test_q1_q2_sequence():
    """Test the exact Q1 → Q2 sequence to isolate the issue."""
    
    print("🔍 TESTING Q1 → Q2 SEQUENCE")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Setup LLM tool (same as your app)
    api_keys = {
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY")
    }
    
    llm_assignments = {
        "question_agent": "openai"
    }
    
    llm_tool = LLMTool(api_keys, llm_assignments)
    
    # Q1 Prompt (exactly like your logs)
    q1_prompt = '''ASSESS Q1: "What is a broad topic you know exceptionally well?"

CRITERIA: Must be SPECIFIC domain/field, not just "business" or "consulting"
Look for: Industry context, expertise indicators, specific skills

SCORE: 1-10 (7+ = advance, <7 = follow-up)
FOLLOW-UP: "What specific area within your expertise do you focus on, and in which industry?"

USER ANSWER: "I solve problems"

Respond with ONLY valid JSON (no markdown):
{"score": X, "needs_follow_up": true/false, "follow_up_question": "...", "reasoning": "..."}'''
    
    # Q2 Prompt (exactly like your logs)
    q2_prompt = '''ASSESS Q2: "What's a niche within that topic where you have even more profound expertise?"

CRITERIA: Must be MORE SPECIFIC than Q1 answer. Look for processes, methods, specialized areas.

SCORE: 1-10 (7+ = advance, <7 = follow-up) 
FOLLOW-UP: "What specific aspect of your expertise do you focus on most?"

USER ANSWER: "so I focus on resource optimization"

Respond with ONLY valid JSON (no markdown):
{"score": X, "needs_follow_up": true/false, "follow_up_question": "...", "reasoning": "..."}'''
    
    print(f"📝 Q1 prompt: {len(q1_prompt)} chars")
    print(f"📝 Q2 prompt: {len(q2_prompt)} chars")
    
    # Test 1: Q1 Only
    print(f"\n🧪 Test 1: Q1 Assessment (should work)")
    try:
        start_time = time.time()
        q1_response = await llm_tool.generate_for_agent(
            "question_agent",
            q1_prompt,
            session_id="test_session_q1",
            temperature=0.1,
            max_tokens=150,
            timeout=15.0
        )
        elapsed = time.time() - start_time
        print(f"✅ Q1 SUCCESS in {elapsed:.2f}s")
        print(f"📝 Q1 Response: {q1_response[:100]}...")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Q1 FAILED after {elapsed:.2f}s: {e}")
        return
    
    # Small delay between calls
    print(f"\n⏱️ Waiting 2 seconds between calls...")
    await asyncio.sleep(2)
    
    # Test 2: Q2 After Q1 (this should fail based on your logs)
    print(f"\n🧪 Test 2: Q2 Assessment (likely to fail)")
    try:
        start_time = time.time()
        q2_response = await llm_tool.generate_for_agent(
            "question_agent",
            q2_prompt,
            session_id="test_session_q2",
            temperature=0.1,
            max_tokens=150,
            timeout=15.0
        )
        elapsed = time.time() - start_time
        print(f"✅ Q2 SUCCESS in {elapsed:.2f}s")
        print(f"📝 Q2 Response: {q2_response[:100]}...")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Q2 FAILED after {elapsed:.2f}s: {e}")
    
    # Test 3: Fresh Q2 Only (new client)
    print(f"\n🧪 Test 3: Fresh Q2 Only (new LLM client)")
    fresh_llm_tool = LLMTool(api_keys, llm_assignments)
    try:
        start_time = time.time()
        fresh_q2_response = await fresh_llm_tool.generate_for_agent(
            "question_agent",
            q2_prompt,
            session_id="fresh_session",
            temperature=0.1,
            max_tokens=150,
            timeout=15.0
        )
        elapsed = time.time() - start_time
        print(f"✅ Fresh Q2 SUCCESS in {elapsed:.2f}s")
        print(f"📝 Fresh Q2 Response: {fresh_q2_response[:100]}...")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ Fresh Q2 FAILED after {elapsed:.2f}s: {e}")

if __name__ == "__main__":
    asyncio.run(test_q1_q2_sequence())
