#!/usr/bin/env python3
"""
Debug script to trace the exact issue with Q2 assessment
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

async def debug_q2_issue():
    """Debug the Q2 assessment issue step by step."""
    
    print("🔍 DEBUGGING Q2 ASSESSMENT ISSUE")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Setup LLM tool
    api_keys = {
        "openai": os.getenv("OPENAI_API_KEY"),
        "anthropic": os.getenv("ANTHROPIC_API_KEY"),
        "deepseek": os.getenv("DEEPSEEK_API_KEY")
    }
    
    llm_assignments = {
        "question_agent": "openai"
    }
    
    print(f"🔧 API Keys available: {[k for k, v in api_keys.items() if v]}")
    
    llm_tool = LLMTool(api_keys, llm_assignments)
    assessment_tool = AssessmentTool(llm_tool)
    
    # Test the exact scenario from the logs
    test_answer = "I help them with planning their resources more effectively"
    
    print(f"\n📝 Testing Q2 assessment with: '{test_answer}'")
    print(f"📏 Answer length: {len(test_answer)} characters")
    
    try:
        print("\n🎯 Starting assessment...")
        result = await assessment_tool.assess_answer(
            2,  # Question 2
            test_answer,
            "question_agent",
            {},  # No context
            "debug_session"
        )
        
        print(f"\n✅ Assessment completed successfully!")
        print(f"📊 Score: {result.get('score', 'N/A')}")
        print(f"🔄 Needs follow-up: {result.get('needs_follow_up', 'N/A')}")
        print(f"💭 Reasoning: {result.get('reasoning', 'N/A')}")
        
    except Exception as e:
        print(f"\n❌ Assessment failed: {e}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_q2_issue())
