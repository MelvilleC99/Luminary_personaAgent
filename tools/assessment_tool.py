"""
Assessment Tool for evaluating answer quality using rubrics.
"""

import json
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class AssessmentTool:
    """Tool for assessing answer quality using detailed rubrics."""
    
    def __init__(self, llm_tool=None):
        """
        Initialize assessment tool.
        
        Args:
            llm_tool: LLM tool for AI-powered assessment
        """
        self.llm_tool = llm_tool
    
    def has_assessment_prompt(self, question_id: int) -> bool:
        """Check if an assessment prompt exists for a question."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "assessment" / f"question_{question_id}_assessment.txt"
        return prompt_path.exists()
    
    async def assess_answer(self, question_id: int, answer: str, 
                          agent_name: str = "assessment_agent",
                          context: Dict[str, Any] = None,
                          session_id: str = None) -> Dict[str, Any]:
        """
        Assess an answer using the appropriate prompt-based rubric.
        
        Args:
            question_id: Question identifier
            answer: User's answer
            agent_name: Name of the agent requesting assessment
            context: Additional context (like previous answers)
            
        Returns:
            Assessment result with score and feedback
        """
        import time
        start_time = time.time()
        logger.info(f"🔍 Assessing Q{question_id}: '{answer[:50]}...'")
        
        # Check if we have a specific assessment prompt for this question
        prompt_path = Path(__file__).parent.parent / "prompts" / "assessment" / f"question_{question_id}_assessment.txt"
        
        if prompt_path.exists():
            logger.info(f"✅ Using LLM assessment prompt for Q{question_id}")
            result = await self._llm_assessment_with_prompt(answer, prompt_path, agent_name, context or {}, session_id)
        else:
            logger.info(f"⚠️ No assessment prompt for Q{question_id}, using basic assessment")
            result = await self._basic_assessment(answer)
        
        assessment_time = time.time() - start_time
        logger.info(f"⏱️ Assessment completed in {assessment_time:.2f}s - Score: {result.get('score')}")
        
        return result
    
    async def _llm_assessment_with_prompt(self, answer: str, prompt_path: Path, 
                                         agent_name: str, context: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Use LLM with specific assessment prompt - streamlined version."""
        
        # Load the assessment prompt
        try:
            with open(prompt_path, 'r') as f:
                assessment_prompt = f.read().strip()
            logger.info(f"📄 Loaded assessment prompt from: {prompt_path}")
            logger.info(f"📄 Raw prompt content: {assessment_prompt[:200]}...")
        except Exception as e:
            logger.error(f"Failed to load assessment prompt: {e}")
            return await self._basic_assessment(answer)
        
        # Simple prompt formatting - just replace user_answer
        try:
            formatted_prompt = assessment_prompt.replace("{user_answer}", answer)
            logger.info(f"🔄 Formatted prompt with user answer")
            logger.info(f"🔄 Final prompt: {formatted_prompt}")
        except Exception as e:
            logger.warning(f"Error formatting prompt: {e}")
            formatted_prompt = f"{assessment_prompt}\n\nUSER ANSWER: {answer}"
        
        # Check prompt size
        prompt_size = len(formatted_prompt)
        logger.info(f"📏 Final prompt size: {prompt_size} characters")
        
        if prompt_size > 1000:  # Even more aggressive limit
            logger.warning(f"⚠️ Prompt over 1000 chars ({prompt_size}), falling back to basic")
            return await self._fast_basic_assessment(answer)
        
        try:
            # Use LLM to assess with very short timeout
            logger.info(f"🤖 Sending assessment request to {agent_name} provider")
            logger.info(f"🤖 Request params: temperature=0.1, max_tokens=150, timeout=15.0")
            
            response = await self.llm_tool.generate_for_agent(
                agent_name, formatted_prompt, session_id=session_id, temperature=0.1, max_tokens=150, timeout=15.0
            )
            
            logger.info(f"📝 LLM response received: {response}")
            
            # Parse the JSON response - handle markdown code blocks
            response_text = response.strip()
            logger.info(f"📝 Raw response: {response_text}")
            
            # Remove markdown code block wrapper if present
            if response_text.startswith('```json'):
                response_text = response_text.replace('```json', '').replace('```', '').strip()
                logger.info(f"🧹 Cleaned response: {response_text}")
            
            result = json.loads(response_text)
            
            # Ensure we have required fields
            if 'score' not in result:
                result['score'] = 5
            if 'needs_follow_up' not in result:
                result['needs_follow_up'] = result.get('score', 5) < 7
            
            logger.info(f"✅ Assessment parsed successfully - Score: {result.get('score')}, Follow-up: {result.get('needs_follow_up')}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Response was: {response}")
            return await self._basic_assessment(answer)
        except Exception as e:
            logger.error(f"LLM assessment failed: {e}")
            logger.info("🔄 Falling back to fast basic assessment...")
            return await self._fast_basic_assessment(answer)
    
    async def _basic_assessment(self, answer: str) -> Dict[str, Any]:
        """Basic assessment for questions without rubrics."""
        
        length = len(answer.strip())
        
        if length < 20:
            score = 3
            category = "poor"
            needs_follow_up = True
        elif length < 50:
            score = 5
            category = "needs_improvement" 
            needs_follow_up = True
        elif length < 100:
            score = 7
            category = "good"
            needs_follow_up = False
        else:
            score = 8
            category = "good"
            needs_follow_up = False
        
        return {
            "score": score,
            "category": category,
            "missing_elements": ["more_detail"] if needs_follow_up else [],
            "strengths": ["appropriate_length"] if not needs_follow_up else [],
            "reasoning": f"Basic length-based assessment: {length} characters",
            "needs_follow_up": needs_follow_up,
            "follow_up_question": "Could you provide more detail to help me better understand?" if needs_follow_up else None
        }
    
    async def _fast_basic_assessment(self, answer: str) -> Dict[str, Any]:
        """Ultra-fast assessment for fallback scenarios - no LLM calls."""
        logger.info("⚡ Performing ultra-fast assessment...")
        
        # Enhanced heuristics - more sophisticated but still fast
        answer_lower = answer.lower().strip()
        word_count = len(answer.split())
        char_count = len(answer_lower)
        
        # Look for specificity indicators
        specific_terms = [
            "manufacturing", "process", "optimization", "systems", "planning", 
            "resources", "efficiency", "lean", "six sigma", "supply chain",
            "inventory", "quality", "production", "operations", "automation"
        ]
        
        specificity_score = sum(1 for term in specific_terms if term in answer_lower)
        
        # Base score calculation
        if word_count < 3:
            base_score = 2
        elif word_count < 8:
            base_score = 4
        elif word_count < 15:
            base_score = 6
        else:
            base_score = 7
        
        # Adjust for specificity
        final_score = min(10, base_score + specificity_score)
        
        # Determine follow-up
        needs_follow_up = final_score < 7
        
        follow_up_question = None
        if needs_follow_up:
            if word_count < 5:
                follow_up_question = "Could you provide more detail about your area of expertise?"
            else:
                follow_up_question = "What specific processes or methods do you use in your work?"
        
        logger.info(f"📊 Fast assessment: {word_count} words, {specificity_score} specific terms, score: {final_score}")
        
        return {
            'score': final_score,
            'needs_follow_up': needs_follow_up,
            'follow_up_question': follow_up_question,
            'reasoning': f"Fast assessment: {word_count} words, {specificity_score} specific terms, score {final_score}/10"
        }
    
    def get_available_questions_with_prompts(self) -> List[int]:
        """Get list of question IDs that have assessment prompts."""
        prompts_dir = Path(__file__).parent.parent / "prompts" / "assessment"
        if not prompts_dir.exists():
            return []
        
        question_ids = []
        for prompt_file in prompts_dir.glob("question_*_assessment.txt"):
            try:
                # Extract question ID from filename like "question_1_assessment.txt"
                question_id = int(prompt_file.stem.split('_')[1])
                question_ids.append(question_id)
            except (ValueError, IndexError):
                continue
        
        return sorted(question_ids)
