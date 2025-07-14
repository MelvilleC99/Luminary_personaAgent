"""
LinkedIn Persona Builder - Conversation Manager

Handles LLM interactions using YAML framework + simple prompt system.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Internal imports
from memory.context_manager import ContextManager, ConversationContext
from memory.llm_cache import LLMCache
from knowledge.framework_loader import FrameworkLoader
from prompts.system_prompts import get_prompt_template

# Configure logging
logger = logging.getLogger(__name__)

# Initialize components
context_manager = ContextManager()
llm_cache = LLMCache()
framework_loader = FrameworkLoader()


@dataclass
class EvaluationResult:
    """Simple evaluation result structure"""
    quality_score: int
    confidence: float
    extracted_info: str
    reasoning: str = ""


class ConversationManager:
    """
    Manages LLM interactions using YAML framework as source of truth.
    
    Uses only TWO prompts:
    1. Greeting prompt for welcome
    2. System prompt for all other tasks (references YAML data)
    """
    
    def __init__(self):
        """Initialize conversation manager"""
        self.context_manager = context_manager
        self.llm_cache = llm_cache
        self.framework_loader = framework_loader
        
        logger.info("ConversationManager initialized with YAML-driven approach")
    
    async def generate_greeting(self, context: Dict[str, Any]) -> str:
        """Generate personalized greeting using greeting prompt"""
        try:
            logger.info("Generating greeting")
            
            greeting_prompt = get_prompt_template("greeting")
            prompt = greeting_prompt.format(
                user_name=context.get("user_name", "there"),
                total_sections=context.get("total_sections", 3),
                estimated_time=context.get("estimated_time", "15-20 minutes"),
                section_overview=context.get("section_overview", "expertise, personality, and positioning")
            )
            
            response = await self.llm_cache.call_llm_with_cache(
                prompt=prompt,
                operation="greeting",
                temperature=0.8,
                max_tokens=300
            )
            
            return response or "Hi! I'm Paul, and I'm here to help you build your LinkedIn persona. Ready to get started?"
            
        except Exception as e:
            logger.error(f"Greeting generation failed: {e}")
            return "Hi! I'm Paul, and I'm here to help you build your LinkedIn persona. Ready to get started?"
    
    async def generate_question(self, criterion: Dict[str, Any], context: ConversationContext) -> str:
        """
        Generate adaptive question using YAML framework + system prompt
        
        Process:
        1. Get question data from YAML framework
        2. Build context from conversation
        3. Use system prompt with task_type="question_generation"
        4. Return adapted question
        """
        try:
            logger.info(f"Generating question for criterion: {criterion.get('name', 'unknown')}")
            
            # Get YAML data
            yaml_question = criterion.get("question", "Tell me about your expertise")
            yaml_good_example = criterion.get("good_example", "")
            yaml_bad_example = criterion.get("bad_example", "")
            criterion_name = criterion.get("name", "")
            
            # Get section info
            section_info = self._get_section_info(criterion_name)
            
            # Use system prompt with question generation task
            system_prompt = get_prompt_template("system")
            prompt = system_prompt.format(
                user_name=context.session_metadata.get("user_name", "there"),
                task_type="question_generation",
                yaml_question=yaml_question,
                yaml_good_example=yaml_good_example,
                yaml_bad_example=yaml_bad_example,
                user_response="",  # Not needed for question generation
                industry=context.industry,
                previous_responses=" | ".join(context.previous_responses[-3:]) if context.previous_responses else "None",
                section_name=section_info.get("name", "Current Section"),
                criterion_name=criterion_name.replace("_", " ").title()
            )
            
            response = await self.llm_cache.call_llm_with_cache(
                prompt=prompt,
                operation="question_generation",
                temperature=0.7,
                max_tokens=300
            )
            
            return response or yaml_question  # Fallback to YAML question
            
        except Exception as e:
            logger.error(f"Question generation failed: {e}")
            return criterion.get("question", "Tell me about your professional expertise.")
    
    async def evaluate_response(self, user_response: str, criterion: Dict[str, Any]) -> EvaluationResult:
        """
        Evaluate response using YAML framework + system prompt
        
        Process:
        1. Get evaluation criteria from YAML
        2. Use system prompt with task_type="response_evaluation"
        3. Parse JSON response
        4. Return evaluation results
        """
        try:
            logger.info(f"Evaluating response for criterion: {criterion.get('name', 'unknown')}")
            
            # Get YAML data
            yaml_good_example = criterion.get("good_example", "")
            yaml_bad_example = criterion.get("bad_example", "")
            criterion_name = criterion.get("name", "")
            
            # Get section info
            section_info = self._get_section_info(criterion_name)
            
            # Use system prompt with evaluation task
            system_prompt = get_prompt_template("system")
            prompt = system_prompt.format(
                user_name="User",  # Not critical for evaluation
                task_type="response_evaluation",
                yaml_question=criterion.get("question", ""),
                yaml_good_example=yaml_good_example,
                yaml_bad_example=yaml_bad_example,
                user_response=user_response,
                industry="unknown",  # Will be improved with context
                previous_responses="",  # Not needed for evaluation
                section_name=section_info.get("name", "Current Section"),
                criterion_name=criterion_name.replace("_", " ").title()
            )
            
            response = await self.llm_cache.parse_json_response(prompt, "response_evaluation")
            
            if response:
                return EvaluationResult(
                    quality_score=response.get("quality_score", 5),
                    confidence=response.get("confidence", 0.5),
                    extracted_info=response.get("extracted_info", user_response[:100]),
                    reasoning=response.get("reasoning", "")
                )
            else:
                return self._fallback_evaluation(user_response)
                
        except Exception as e:
            logger.error(f"Response evaluation failed: {e}")
            return self._fallback_evaluation(user_response)
    
    async def generate_follow_up(self, session_id: str, criterion: Dict[str, Any], 
                               original_response: str, attempt_number: int) -> str:
        """Generate follow-up question using YAML examples + system prompt"""
        try:
            logger.info(f"Generating follow-up for {criterion.get('name', 'unknown')}, attempt {attempt_number}")
            
            # Get context
            context = await self.context_manager.build_question_context(session_id)
            
            # Get YAML data
            yaml_good_example = criterion.get("good_example", "")
            yaml_bad_example = criterion.get("bad_example", "")
            follow_up_example = criterion.get("follow_up_example", "")
            criterion_name = criterion.get("name", "")
            
            # Get section info
            section_info = self._get_section_info(criterion_name)
            
            # Use system prompt with follow-up task
            system_prompt = get_prompt_template("system")
            prompt = system_prompt.format(
                user_name=context.session_metadata.get("user_name", "there"),
                task_type="follow_up",
                yaml_question=criterion.get("question", ""),
                yaml_good_example=yaml_good_example + (f" | Follow-up template: {follow_up_example}" if follow_up_example else ""),
                yaml_bad_example=yaml_bad_example,
                user_response=original_response,
                industry=context.industry,
                previous_responses="",
                section_name=section_info.get("name", "Current Section"),
                criterion_name=criterion_name.replace("_", " ").title()
            )
            
            response = await self.llm_cache.call_llm_with_cache(
                prompt=prompt,
                operation="follow_up",
                temperature=0.7,
                max_tokens=400
            )
            
            return response or f"Could you be more specific about {criterion_name.replace('_', ' ')}? For example: {yaml_good_example}"
            
        except Exception as e:
            logger.error(f"Follow-up generation failed: {e}")
            return f"Could you be more specific? For example: {criterion.get('good_example', 'your expertise')}"
    
    async def generate_section_transition(self, completed_section: int, 
                                        section_summary: str, next_section: int,
                                        user_name: str = "there") -> str:
        """Generate section transition using system prompt"""
        try:
            logger.info(f"Generating transition from section {completed_section} to {next_section}")
            
            # Get section info from framework
            current_section_data = self.framework_loader.get_section(completed_section)
            next_section_data = self.framework_loader.get_section(next_section)
            
            current_name = current_section_data.name if current_section_data else f"Section {completed_section}"
            next_name = next_section_data.name if next_section_data else f"Section {next_section}"
            next_objective = next_section_data.objective if next_section_data else "Continue building your persona"
            
            # Use system prompt with transition task
            system_prompt = get_prompt_template("system")
            prompt = system_prompt.format(
                user_name=user_name,
                task_type="section_transition",
                yaml_question=f"Transition from {current_name} to {next_name}",
                yaml_good_example=section_summary,
                yaml_bad_example="",
                user_response="",
                industry="",
                previous_responses="",
                section_name=next_name,
                criterion_name=next_objective
            )
            
            response = await self.llm_cache.call_llm_with_cache(
                prompt=prompt,
                operation="section_transition",
                temperature=0.7,
                max_tokens=300
            )
            
            return response or f"Great work on {current_name}! Now let's move to {next_name}: {next_objective}"
            
        except Exception as e:
            logger.error(f"Section transition generation failed: {e}")
            return f"Great progress! Let's continue to the next section."
    
    async def generate_persona_summary(self, persona_data: Dict[str, Any], user_name: str = "User") -> str:
        """Generate final persona summary using system prompt"""
        try:
            logger.info("Generating persona summary")
            
            # Extract key information from persona data
            summary_context = self._extract_persona_context(persona_data)
            
            # Use system prompt with summary task
            system_prompt = get_prompt_template("system")
            prompt = system_prompt.format(
                user_name=user_name,
                task_type="persona_summary",
                yaml_question="Create comprehensive LinkedIn persona summary",
                yaml_good_example=summary_context,
                yaml_bad_example="",
                user_response="",
                industry=persona_data.get("detected_industry", "unknown"),
                previous_responses="",
                section_name="Final Summary",
                criterion_name="Complete LinkedIn Persona"
            )
            
            response = await self.llm_cache.call_llm_with_cache(
                prompt=prompt,
                operation="persona_summary",
                temperature=0.6,
                max_tokens=800
            )
            
            return response or f"Your LinkedIn persona for {user_name} has been completed successfully."
            
        except Exception as e:
            logger.error(f"Persona summary generation failed: {e}")
            return f"Your LinkedIn persona has been completed successfully, {user_name}!"
    
    def _fallback_evaluation(self, user_response: str) -> EvaluationResult:
        """Simple fallback evaluation based on response length"""
        response_length = len(user_response.strip().split())
        
        if response_length < 3:
            quality_score = 2
            confidence = 0.8
        elif response_length < 8:
            quality_score = 4
            confidence = 0.6
        elif response_length < 15:
            quality_score = 6
            confidence = 0.5
        else:
            quality_score = 7
            confidence = 0.4
        
        return EvaluationResult(
            quality_score=quality_score,
            confidence=confidence,
            extracted_info=user_response[:100],
            reasoning="Fallback evaluation based on response length"
        )
    
    def _get_section_info(self, criterion_name: str) -> Dict[str, str]:
        """Get section information for a given criterion"""
        try:
            # This would normally come from framework, simplified for now
            section_map = {
                "broad_domain_expertise": {"name": "Core Expertise & Ideal Customer"},
                "specific_niche_focus": {"name": "Core Expertise & Ideal Customer"},
                "ideal_client_definition": {"name": "Core Expertise & Ideal Customer"},
                "professional_communication_style": {"name": "Brand Personality & Communication Style"},
                "content_approach": {"name": "Brand Personality & Communication Style"},
                "unique_value_proposition": {"name": "Positioning & Value Proposition"},
                "competitive_differentiator": {"name": "Positioning & Value Proposition"}
            }
            
            return section_map.get(criterion_name, {"name": "Current Section"})
            
        except Exception as e:
            logger.error(f"Section info lookup failed: {e}")
            return {"name": "Current Section"}
    
    def _extract_persona_context(self, persona_data: Dict[str, Any]) -> str:
        """Extract key context from persona data for summary"""
        try:
            context_parts = []
            
            sections = persona_data.get("sections", [])
            for section in sections:
                criteria = section.get("criteria", {})
                for criterion_name, criterion_data in criteria.items():
                    if criterion_data.get("complete", False):
                        response = criterion_data.get("response", "")
                        if response:
                            context_parts.append(f"{criterion_name}: {response}")
            
            return " | ".join(context_parts[:10])  # Limit context length
            
        except Exception as e:
            logger.error(f"Context extraction failed: {e}")
            return "User expertise and professional background"


# Global conversation manager instance
conversation_manager = ConversationManager()
