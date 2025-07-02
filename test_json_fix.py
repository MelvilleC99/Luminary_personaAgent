#!/usr/bin/env python3
"""
Test the JSON parsing fix
"""

import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from tools.llm_tool import LLMTool
from tools.assessment_tool import AssessmentTool

async def test_json_fix():
    """Test that JSON parsing now works correctly."""
    
    print("🔍 TESTING JSON PARSING FIX")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Setup LLM tool
    api_keys = {
        "openai": os.getenv("OPENAI_API_KEY"),
    }
    
    llm_assignments = {
        "question_agent": "openai"
    }
    
    llm_tool = LLMTool(api_keys, llm_assignments)
    assessment_tool = AssessmentTool(llm_tool)
    
    # Test scenarios from the actual conversation
    test_cases = [
        {
            "question": 1,
            "answer": "I solve problems in manufacturing",
            "expected": "Should work now with JSON parsing"
        },
        {
            "question": 2, 
            "answer": "I help them with planning their resources more effectively",
            "expected": "Should work now - this was the failing case"
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n🧪 Test {i}: Q{test['question']}")
        print(f"📝 Answer: '{test['answer']}'")
        print(f"🎯 Expected: {test['expected']}")
        
        try:
            result = await assessment_tool.assess_answer(
                test['question'],
                test['answer'],
                "question_agent", 
                {},
                "test_session"
            )
            
            print(f"✅ SUCCESS!")
            print(f"📊 Score: {result.get('score', 'N/A')}")
            print(f"🔄 Needs follow-up: {result.get('needs_follow_up', 'N/A')}")
            print(f"❓ Follow-up question: {result.get('follow_up_question', 'N/A')[:50]}...")
            print(f"💭 Reasoning: {result.get('reasoning', 'N/A')[:50]}...")
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_json_fix())
