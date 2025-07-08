"""
Framework Assessment Tool for comprehensive persona framework evaluation.
"""

import logging
import yaml
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from tools.information_extraction_tool import InformationExtractionTool

logger = logging.getLogger(__name__)


class FrameworkAssessmentTool:
    """Tool for assessing framework completion and generating next conversation steps."""
    
    def __init__(self, llm_tool=None):
        """Initialize the framework assessment tool."""
        self.llm_tool = llm_tool
        self.information_extractor = InformationExtractionTool(llm_tool)
        self.framework_criteria = self._load_framework_criteria()
        
    def _load_framework_criteria(self) -> Dict[str, Any]:
        """Load framework criteria from YAML file."""
        try:
            criteria_path = Path(__file__).parent.parent / "knowledge" / "framework_criteria.yaml"
            with open(criteria_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load framework criteria: {e}")
            return {}
    
    async def assess_response(self, user_response: str, session_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive assessment of user response against framework.
        
        Args:
            user_response: User's conversational response
            session_state: Current session state with extracted information
            
        Returns:
            Assessment result with next conversation steps
        """
        logger.info(f"Assessing response: '{user_response[:100]}...'")
        
        try:
            # Extract information from the response
            extraction_result = await self.information_extractor.extract_information(
                user_response, session_state
            )
            
            if "error" in extraction_result:
                return {"error": extraction_result["error"]}
            
            # Update session state with new extractions
            updated_state = self._update_session_state(session_state, extraction_result)
            
            # Get completion status
            completion_status = self.information_extractor.get_completion_status(updated_state)
            
            # Determine next conversation action
            next_action = await self._determine_next_action(
                extraction_result, updated_state, completion_status
            )
            
            return {
                "extractions": extraction_result["extractions"],
                "updated_state": updated_state,
                "completion_status": completion_status,
                "next_action": next_action,
                "assessment_summary": {
                    "new_extractions": len(extraction_result["extractions"]),
                    "overall_completion": completion_status["overall_completion"],
                    "response_quality": self._assess_response_quality(extraction_result)
                }
            }
            
        except Exception as e:
            logger.error(f"Framework assessment failed: {e}")
            return {"error": str(e)}
    
    def _update_session_state(self, current_state: Dict[str, Any], 
                            extraction_result: Dict[str, Any]) -> Dict[str, Any]:
        """Update session state with new extractions."""
        updated_state = current_state.copy()
        
        # Initialize extracted_information if not present
        if "extracted_information" not in updated_state:
            updated_state["extracted_information"] = {}
        
        # Process each extraction
        for extraction in extraction_result["extractions"]:
            section = extraction["framework_section"]
            criteria = extraction["criteria_key"]
            
            # Initialize section if not present
            if section not in updated_state["extracted_information"]:
                updated_state["extracted_information"][section] = {}
            
            # Update or add the criteria
            updated_state["extracted_information"][section][criteria] = {
                "value": extraction["extracted_value"],
                "confidence": extraction.get("confidence_score", 0.0),
                "reasoning": extraction.get("reasoning", ""),
                "extracted_at": "current_turn",  # Would be actual timestamp in real implementation
                "needs_follow_up": extraction.get("needs_follow_up", False)
            }
        
        return updated_state
    
    def _assess_response_quality(self, extraction_result: Dict[str, Any]) -> str:
        """Assess the quality of the user's response."""
        extractions = extraction_result.get("extractions", [])
        
        if not extractions:
            return "surface"  # No meaningful information extracted
        
        # Calculate average confidence
        avg_confidence = sum(e.get("confidence_score", 0.0) for e in extractions) / len(extractions)
        
        if avg_confidence >= 0.8:
            return "excellent"
        elif avg_confidence >= 0.6:
            return "good"
        else:
            return "surface"
    
    async def _determine_next_action(self, extraction_result: Dict[str, Any], 
                                   updated_state: Dict[str, Any], 
                                   completion_status: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the next conversation action."""
        
        # If overall completion is high, consider wrapping up
        if completion_status["overall_completion"] >= 90:  # Raised from 80% to 90%
            return await self._generate_completion_action(updated_state)
        
        # Check if we need follow-up on current extractions
        needs_follow_up = any(
            e.get("needs_follow_up", False) for e in extraction_result.get("extractions", [])
        )
        
        if needs_follow_up:
            return await self._generate_follow_up_action(extraction_result, updated_state)
        
        # If response was rich, confirm and transition to next area
        if self._assess_response_quality(extraction_result) in ["good", "excellent"]:
            return await self._generate_confirmation_and_transition(extraction_result, updated_state)
        
        # If response was surface-level, seek more depth
        return await self._generate_depth_seeking_action(extraction_result, updated_state)
    
    async def _generate_follow_up_action(self, extraction_result: Dict[str, Any], 
                                       updated_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate follow-up action for insufficient extractions."""
        
        # Find the extraction that needs follow-up
        follow_up_extraction = None
        for extraction in extraction_result.get("extractions", []):
            if extraction.get("needs_follow_up", False):
                follow_up_extraction = extraction
                break
        
        if not follow_up_extraction:
            return {"action": "continue", "message": "Could you elaborate on that?"}
        
        # Get criteria info for better follow-up
        section = follow_up_extraction["framework_section"]
        criteria = follow_up_extraction["criteria_key"]
        
        criteria_info = self.framework_criteria.get("framework_sections", {}).get(section, {}).get("criteria", {}).get(criteria, {})
        
        # Use LLM to generate contextual follow-up
        follow_up_prompt = f"""
Generate a natural follow-up question to get more specific information.

CONTEXT:
- Framework Section: {section}
- Criteria: {criteria}
- User's Response: "{follow_up_extraction['extracted_value']}"
- Confidence Score: {follow_up_extraction.get('confidence_score', 0.0)}

CRITERIA DESCRIPTION: {criteria_info.get('description', '')}

EXAMPLES OF GOOD ANSWERS:
{criteria_info.get('examples', {}).get('good', [])}

EXAMPLES OF INSUFFICIENT ANSWERS:
{criteria_info.get('examples', {}).get('bad', [])}

Generate a warm, conversational follow-up question that:
1. Acknowledges what they shared
2. Asks for more specificity or detail
3. Feels natural and encouraging
4. Helps them understand what level of detail you need

RESPOND WITH JUST THE FOLLOW-UP QUESTION - NO EXTRA TEXT.
"""
        
        try:
            follow_up_message = await self.llm_tool.generate_for_agent(
                "framework_assessor",
                follow_up_prompt,
                temperature=0.3,
                max_tokens=200
            )
            
            return {
                "action": "follow_up",
                "message": follow_up_message.strip(),
                "focus_section": section,
                "focus_criteria": criteria,
                "type": "depth_seeking"
            }
            
        except Exception as e:
            logger.error(f"Failed to generate follow-up: {e}")
            return {
                "action": "follow_up",
                "message": "Could you give me a bit more detail on that? I want to make sure I capture the specifics.",
                "focus_section": section,
                "focus_criteria": criteria,
                "type": "depth_seeking"
            }
    
    async def _generate_confirmation_and_transition(self, extraction_result: Dict[str, Any], 
                                                  updated_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate confirmation and transition to next area."""
        
        # Find the most important area to transition to
        missing_criteria = self.information_extractor.get_missing_criteria(updated_state)
        
        if not missing_criteria:
            return await self._generate_completion_action(updated_state)
        
        # Use simple, natural conversation flow
        from tools.conversation_helpers import get_natural_follow_up
        
        next_message = get_natural_follow_up(
            extraction_result.get("extractions", []), 
            missing_criteria
        )
        
        next_focus = missing_criteria[0] if missing_criteria else None
        
        return {
            "action": "confirm_and_transition",
            "message": next_message,
            "focus_section": next_focus["framework_section"] if next_focus else None,
            "focus_criteria": next_focus["criteria_key"] if next_focus else None,
            "type": "transition"
        }
    
    async def _generate_depth_seeking_action(self, extraction_result: Dict[str, Any], 
                                           updated_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate action to seek more depth on current topic."""
        
        # Get conversation patterns for depth seeking
        patterns = self.framework_criteria.get("conversation_patterns", {})
        depth_patterns = patterns.get("depth_seeking", [
            "Can you give me a specific example of that?",
            "What does that look like in practice?",
            "Tell me more about how that works..."
        ])
        
        # Use a depth-seeking pattern
        import random
        depth_message = random.choice(depth_patterns)
        
        return {
            "action": "seek_depth",
            "message": depth_message,
            "type": "depth_seeking"
        }
    
    async def _generate_completion_action(self, updated_state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate completion action when framework is sufficiently complete."""
        
        completion_status = self.information_extractor.get_completion_status(updated_state)
        
        completion_message = f"""
Excellent! I've gathered comprehensive information about your brand persona across all the key areas.

Based on our conversation, I have a clear picture of:
• Your expertise and ideal customer profile
• Your brand personality and values
• Your unique positioning and approach
• Your communication style and voice
• Your content goals and audience insights
• Your long-term vision and success metrics

I'm now ready to create your comprehensive persona document. This will include strategic positioning, target audience psychology, brand voice guidelines, and content recommendations tailored specifically to your business.

Would you like me to generate your complete persona now, or is there anything else you'd like to add or clarify?
"""
        
        return {
            "action": "completion",
            "message": completion_message.strip(),
            "completion_percentage": completion_status["overall_completion"],
            "type": "completion"
        }
    
    def get_conversation_suggestions(self, session_state: Dict[str, Any]) -> List[str]:
        """Get suggested conversation starters based on current state."""
        
        missing_criteria = self.information_extractor.get_missing_criteria(session_state)
        
        if not missing_criteria:
            return ["Ready to generate your persona!"]
        
        # Get conversation starters for top missing criteria
        suggestions = []
        for criteria in missing_criteria[:3]:  # Top 3 missing
            starters = criteria.get("conversation_starters", [])
            if starters:
                suggestions.append(starters[0])
        
        return suggestions
    
    def get_framework_progress_summary(self, session_state: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of framework progress for display."""
        
        completion_status = self.information_extractor.get_completion_status(session_state)
        
        # Create section summaries
        section_summaries = {}
        for section_name, section_status in completion_status["section_completion"].items():
            # Get section display name
            section_info = self.framework_criteria.get("framework_sections", {}).get(section_name, {})
            display_name = section_info.get("section_name", section_name)
            
            section_summaries[display_name] = {
                "completion_percentage": round(section_status["completion_percentage"], 1),
                "completed_criteria": section_status["completed_criteria"],
                "total_criteria": section_status["total_criteria"],
                "status": self._get_section_status(section_status["completion_percentage"])
            }
        
        return {
            "overall_completion": round(completion_status["overall_completion"], 1),
            "total_criteria": completion_status["total_criteria"],
            "completed_criteria": completion_status["completed_criteria"],
            "missing_criteria": completion_status["missing_criteria"],
            "insufficient_criteria": completion_status["insufficient_criteria"],
            "section_summaries": section_summaries,
            "next_focus": self._get_next_focus_area(session_state)
        }
    
    def _get_section_status(self, completion_percentage: float) -> str:
        """Get status description for a section."""
        if completion_percentage >= 80:
            return "complete"
        elif completion_percentage >= 50:
            return "in_progress"
        elif completion_percentage > 0:
            return "started"
        else:
            return "not_started"
    
    def _get_next_focus_area(self, session_state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get the next area to focus on."""
        missing_criteria = self.information_extractor.get_missing_criteria(session_state)
        
        if not missing_criteria:
            return None
        
        next_focus = missing_criteria[0]
        
        # Get section display name
        section_info = self.framework_criteria.get("framework_sections", {}).get(
            next_focus["framework_section"], {}
        )
        
        return {
            "section": section_info.get("section_name", next_focus["framework_section"]),
            "criteria": next_focus["criteria_key"],
            "description": next_focus["description"],
            "conversation_starters": next_focus.get("conversation_starters", []),
            "priority": next_focus["priority"]
        }
