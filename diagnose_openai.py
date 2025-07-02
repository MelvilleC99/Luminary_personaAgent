#!/usr/bin/env python3
"""
Diagnose OpenAI API issues
"""

import asyncio
import sys
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent))

import openai

async def diagnose_openai():
    """Diagnose OpenAI API issues."""
    
    print("🔍 DIAGNOSING OPENAI API ISSUES")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ No OpenAI API key found!")
        return
    
    print(f"🔑 API Key present: {api_key[:8]}...{api_key[-4:]}")
    
    # Initialize client
    client = openai.AsyncOpenAI(api_key=api_key)
    
    # Test 1: Simple request
    print("\n🧪 Test 1: Simple 'Hello' request")
    try:
        start_time = time.time()
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10,
            timeout=10.0
        )
        elapsed = time.time() - start_time
        print(f"✅ SUCCESS in {elapsed:.2f}s: {response.choices[0].message.content}")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ FAILED after {elapsed:.2f}s: {e}")
    
    # Test 2: Different model
    print("\n🧪 Test 2: Try GPT-3.5-turbo instead")
    try:
        start_time = time.time()
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10,
            timeout=10.0
        )
        elapsed = time.time() - start_time
        print(f"✅ SUCCESS in {elapsed:.2f}s: {response.choices[0].message.content}")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ FAILED after {elapsed:.2f}s: {e}")
    
    # Test 3: Your actual assessment prompt
    print("\n🧪 Test 3: Your actual Q2 assessment prompt")
    actual_prompt = '''ASSESS Q2: "What's a niche within that topic where you have even more profound expertise?"

CRITERIA: Must be MORE SPECIFIC than Q1 answer. Look for processes, methods, specialized areas.

SCORE: 1-10 (7+ = advance, <7 = follow-up) 
FOLLOW-UP: "What specific aspect of your expertise do you focus on most?"

USER ANSWER: "I help them with planning their resources more effectively"

Respond with ONLY valid JSON (no markdown):
{"score": X, "needs_follow_up": true/false, "follow_up_question": "...", "reasoning": "..."}'''
    
    try:
        start_time = time.time()
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": actual_prompt}],
            max_tokens=150,
            temperature=0.1,
            timeout=15.0
        )
        elapsed = time.time() - start_time
        print(f"✅ SUCCESS in {elapsed:.2f}s")
        print(f"📝 Response: {response.choices[0].message.content}")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"❌ FAILED after {elapsed:.2f}s: {e}")
        print(f"❌ Error type: {type(e).__name__}")
    
    # Test 4: Check account limits
    print("\n🧪 Test 4: Check API usage/limits")
    try:
        # This endpoint might not be available in all accounts
        print("ℹ️ Cannot programmatically check usage limits")
        print("ℹ️ Please check: https://platform.openai.com/usage")
        print("ℹ️ Check for:")
        print("   - Rate limits exceeded")
        print("   - Quota exhausted") 
        print("   - Payment issues")
        print("   - Account restrictions")
    except Exception as e:
        print(f"⚠️ Cannot check limits: {e}")

if __name__ == "__main__":
    asyncio.run(diagnose_openai())
