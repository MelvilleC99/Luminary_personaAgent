#!/usr/bin/env python3
"""
Test database interference with OpenAI calls
"""

import asyncio
import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from database.supabase_client import SupabaseClient
from tools.llm_tool import LLMTool
from orchestrator.config import settings

async def test_database_interference():
    """Test if database operations interfere with OpenAI calls."""
    
    print("🔍 TESTING DATABASE INTERFERENCE")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Initialize database (like your app)
    database = SupabaseClient(settings.supabase_url, settings.supabase_key)
    
    # Initialize LLM with database (like your app) 
    llm_tool = LLMTool(
        api_keys=settings.api_keys,
        llm_assignments=settings.llm_config,
        database=database  # This is the key difference!
    )
    
    q2_prompt = '''ASSESS Q2: "What's a niche within that topic where you have even more profound expertise?"

CRITERIA: Must be MORE SPECIFIC than Q1 answer. Look for processes, methods, specialized areas.

SCORE: 1-10 (7+ = advance, <7 = follow-up) 
FOLLOW-UP: "What specific aspect of your expertise do you focus on most?"

USER ANSWER: "so I focus on resource optimization"

Respond with ONLY valid JSON (no markdown):
{"score": X, "needs_follow_up": true/false, "follow_up_question": "...", "reasoning": "..."}'''
    
    # Test 1: With database attached (like your app)
    print(f"\n🧪 Test 1: LLM with database attached (like your app)")
    try:
        start_time = time.time()
        response = await llm_tool.generate_for_agent(
            "question_agent",
            q2_prompt,
            session_id="test_session_with_db",
            temperature=0.1,
            max_tokens=150,
            timeout=15.0
        )
        elapsed = time.time() - start_time
        print(f"✅ SUCCESS in {elapsed:.2f}s with database")
        print(f"📝 Response: {response[:100]}...")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ FAILED after {elapsed:.2f}s with database: {e}")
    
    # Test 2: Without database (like our standalone tests)
    print(f"\n🧪 Test 2: LLM without database (like standalone tests)")
    standalone_llm = LLMTool(
        api_keys=settings.api_keys,
        llm_assignments=settings.llm_config,
        database=None  # No database!
    )
    
    try:
        start_time = time.time()
        response = await standalone_llm.generate_for_agent(
            "question_agent",
            q2_prompt,
            session_id="test_session_no_db",
            temperature=0.1,
            max_tokens=150,
            timeout=15.0
        )
        elapsed = time.time() - start_time
        print(f"✅ SUCCESS in {elapsed:.2f}s without database")
        print(f"📝 Response: {response[:100]}...")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ FAILED after {elapsed:.2f}s without database: {e}")

if __name__ == "__main__":
    asyncio.run(test_database_interference())
