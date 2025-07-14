"""
LinkedIn Persona Builder - Validation Manager

Ensures consistency using YAML framework + simple system prompt.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

# Internal imports
from memory.llm_cache import LLMCache
from prompts.system_prompts import get_prompt_template

# Configure logging
logger = logging.getLogger(__name__)

# Initialize components
llm_cache = LLMCache()


@dataclass
class ValidationResult:
    """Simple validation result structure"""
    valid: bool
    conflicts: List[str] = None
    confidence: float = 1.0
    
    def __post_init__(self):
        if self.conflicts is None:
            self.conflicts = []


class ValidationManager:
    """
    Validates persona data consistency using YAML framework + system prompt.
    
    Uses the system prompt with task_type="contradiction_check" for consistency validation.
    Simple keyword-based fallbacks for basic validation.
    """
    
    def __init__(self):
        """Initialize validation manager"""
        self.llm_cache = llm_cache
        
        logger.info("ValidationManager initialized with system prompt approach")
    
    async def validate_consistency(self, new_evaluation: Dict[str, Any], 
                                 existing_persona: Dict[str, Any]) -> ValidationResult:
        """
        Check for contradictions in persona data using system prompt
        
        Process:
        1. Extract key information from new evaluation
        2. Compare against existing persona data
        3. Use system prompt to check for contradictions
        4. Return validation result
        """
        try:
            logger.info("Validating persona consistency")
            
            if not existing_persona or not new_evaluation:
                return ValidationResult(valid=True)
            
            # Extract new information
            new_info = new_evaluation.get("extracted_info", "")
            if not new_info.strip():
                return ValidationResult(valid=True)
            
            # Find potential conflicts in existing data
            conflicts = await self._find_potential_conflicts(new_info, existing_persona)
            
            if not conflicts:
                return ValidationResult(valid=True)
            
            # Check each potential conflict using system prompt
            confirmed_conflicts = []
            for conflict in conflicts:
                is_contradiction = await self._check_contradiction_with_system_prompt(
                    existing_info=conflict["existing_info"],
                    new_info=new_info,
                    existing_criterion=conflict["criterion_name"],
                    new_criterion="current_response"
                )
                
                if is_contradiction["contradicts"]:
                    confirmed_conflicts.append(f"Conflict: {conflict['criterion_name']} - {is_contradiction['reasoning']}")
            
            return ValidationResult(
                valid=len(confirmed_conflicts) == 0,
                conflicts=confirmed_conflicts,
                confidence=0.8
            )
            
        except Exception as e:
            logger.error(f"Consistency validation failed: {e}")
            return ValidationResult(valid=True)  # Default to valid on error
    
    async def _find_potential_conflicts(self, new_info: str, existing_persona: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find potential conflicts using simple keyword analysis"""
        try:
            potential_conflicts = []
            new_info_lower = new_info.lower()
            
            # Extract completed responses from existing persona
            sections = existing_persona.get("sections", [])
            for section in sections:
                criteria = section.get("criteria", {})
                for criterion_name, criterion_data in criteria.items():
                    if criterion_data.get("complete", False):
                        existing_response = criterion_data.get("response", "")
                        
                        # Simple conflict detection patterns
                        if self._might_conflict(new_info_lower, existing_response.lower()):
                            potential_conflicts.append({
                                "criterion_name": criterion_name,
                                "existing_info": existing_response,
                                "section": section.get("section_name", "Unknown")
                            })
            
            return potential_conflicts
            
        except Exception as e:
            logger.error(f"Conflict detection failed: {e}")
            return []
    
    def _might_conflict(self, new_info: str, existing_info: str) -> bool:
        """Simple heuristic to detect potential conflicts"""
        try:
            # Keywords that might indicate contradictory business models
            b2b_keywords = ["b2b", "business to business", "enterprise", "corporate"]
            b2c_keywords = ["b2c", "business to consumer", "consumer", "retail", "individual"]
            
            # Experience level conflicts
            beginner_keywords = ["new", "starting", "beginner", "just started"]
            experienced_keywords = ["years", "decade", "experienced", "veteran", "senior"]
            
            # Check for B2B vs B2C conflict
            new_has_b2b = any(keyword in new_info for keyword in b2b_keywords)
            new_has_b2c = any(keyword in new_info for keyword in b2c_keywords)
            existing_has_b2b = any(keyword in existing_info for keyword in b2b_keywords)
            existing_has_b2c = any(keyword in existing_info for keyword in b2c_keywords)
            
            if (new_has_b2b and existing_has_b2c) or (new_has_b2c and existing_has_b2b):
                return True
            
            # Check for experience level conflicts
            new_has_beginner = any(keyword in new_info for keyword in beginner_keywords)
            new_has_experienced = any(keyword in new_info for keyword in experienced_keywords)
            existing_has_beginner = any(keyword in existing_info for keyword in beginner_keywords)
            existing_has_experienced = any(keyword in existing_info for keyword in experienced_keywords)
            
            if (new_has_beginner and existing_has_experienced) or (new_has_experienced and existing_has_beginner):
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Conflict heuristic failed: {e}")
            return False
    
    async def _check_contradiction_with_system_prompt(self, existing_info: str, new_info: str,
                                                    existing_criterion: str, new_criterion: str) -> Dict[str, Any]:
        """Use system prompt to check for contradictions"""
        try:
            # Use system prompt with contradiction check task
            system_prompt = get_prompt_template("system")
            prompt = system_prompt.format(
                user_name="User",
                task_type="contradiction_check",
                yaml_question=f"Do these statements contradict each other?",
                yaml_good_example=f"Existing: {existing_info}",
                yaml_bad_example=f"New: {new_info}",
                user_response="",
                industry="unknown",
                previous_responses="",
                section_name="Consistency Check",
                criterion_name=f"Compare {existing_criterion} vs {new_criterion}"
            )
            
            # Add specific contradiction checking instructions
            contradiction_prompt = prompt + """

Check if these two pieces of information contradict each other:

Existing information: "{existing_info}" (from {existing_criterion})
New information: "{new_info}" (from {new_criterion})

Consider:
1. Do these statements directly contradict each other?
2. Could both be true in different contexts?
3. Is this a significant inconsistency that needs resolution?

Examples of contradictions:
- "I work with B2B companies" vs "I focus on B2C retail customers"
- "I'm a beginner" vs "10 years of experience"

Examples of NOT contradictions:
- "I do marketing" vs "I specialize in email campaigns" (second is more specific)
- "I work with startups" vs "I help growth-stage companies" (could overlap)

Return ONLY valid JSON:
{{
  "contradicts": [true/false],
  "confidence": [0.0-1.0 float],
  "reasoning": "[explanation of why they do/don't contradict]"
}}
""".format(
                existing_info=existing_info,
                new_info=new_info,
                existing_criterion=existing_criterion,
                new_criterion=new_criterion
            )
            
            result = await self.llm_cache.parse_json_response(contradiction_prompt, "contradiction_check")
            
            if result:
                return result
            else:
                # Fallback to simple keyword-based contradiction detection
                return self._simple_contradiction_check(existing_info, new_info)
                
        except Exception as e:
            logger.error(f"System prompt contradiction check failed: {e}")
            return self._simple_contradiction_check(existing_info, new_info)
    
    def _simple_contradiction_check(self, existing_info: str, new_info: str) -> Dict[str, Any]:
        """Simple contradiction detection using keywords"""
        try:
            existing_lower = existing_info.lower()
            new_lower = new_info.lower()
            
            # Check for obvious contradictions
            contradicts = False
            reasoning = "No obvious contradiction detected"
            
            # B2B vs B2C check
            if (("b2b" in existing_lower or "business to business" in existing_lower) and 
                ("b2c" in new_lower or "consumer" in new_lower)):
                contradicts = True
                reasoning = "Business model contradiction: B2B vs B2C"
            elif (("b2c" in existing_lower or "consumer" in existing_lower) and 
                  ("b2b" in new_lower or "business to business" in new_lower)):
                contradicts = True
                reasoning = "Business model contradiction: B2C vs B2B"
            
            # Experience level check
            elif (("beginner" in existing_lower or "new" in existing_lower) and 
                  ("years" in new_lower or "experienced" in new_lower)):
                contradicts = True
                reasoning = "Experience level contradiction: beginner vs experienced"
            elif (("years" in existing_lower or "experienced" in existing_lower) and 
                  ("beginner" in new_lower or "new" in new_lower)):
                contradicts = True
                reasoning = "Experience level contradiction: experienced vs beginner"
            
            return {
                "contradicts": contradicts,
                "confidence": 0.7 if contradicts else 0.5,
                "reasoning": reasoning
            }
            
        except Exception as e:
            logger.error(f"Simple contradiction check failed: {e}")
            return {
                "contradicts": False,
                "confidence": 0.0,
                "reasoning": "Error in contradiction detection"
            }
    
    async def validate_persona_completeness(self, persona_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate persona completeness using simple analysis"""
        try:
            logger.info("Validating persona completeness")
            
            if not persona_data:
                return {
                    "overall_valid": False,
                    "completeness_score": 0.0,
                    "missing_critical_info": ["No persona data found"],
                    "recommendations": ["Complete the persona building process"]
                }
            
            # Simple completeness analysis
            sections = persona_data.get("sections", [])
            total_criteria = 0
            completed_criteria = 0
            missing_info = []
            
            for section in sections:
                criteria = section.get("criteria", {})
                section_name = section.get("section_name", "Unknown Section")
                
                for criterion_name, criterion_data in criteria.items():
                    total_criteria += 1
                    
                    if criterion_data.get("complete", False):
                        completed_criteria += 1
                    else:
                        missing_info.append(f"{section_name}: {criterion_name.replace('_', ' ').title()}")
            
            completeness_score = completed_criteria / total_criteria if total_criteria > 0 else 0.0
            
            # Generate recommendations
            recommendations = []
            if completeness_score < 0.7:
                recommendations.append("Complete more criteria to strengthen your persona")
            if completeness_score < 0.9:
                recommendations.append("Add more specific details to incomplete sections")
            if completeness_score >= 0.9:
                recommendations.append("Your persona is well-developed and ready for LinkedIn")
            
            return {
                "overall_valid": completeness_score >= 0.7,
                "completeness_score": completeness_score,
                "missing_critical_info": missing_info[:5],  # Top 5 missing items
                "quality_issues": [],  # Could add quality analysis here
                "recommendations": recommendations
            }
            
        except Exception as e:
            logger.error(f"Completeness validation failed: {e}")
            return {
                "overall_valid": False,
                "completeness_score": 0.0,
                "missing_critical_info": ["Validation failed"],
                "recommendations": ["Try again"]
            }


# Global validation manager instance
validation_manager = ValidationManager()
