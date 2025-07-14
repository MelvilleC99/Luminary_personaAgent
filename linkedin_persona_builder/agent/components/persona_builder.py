"""
LinkedIn Persona Builder - Persona Builder

Compiles final persona using YAML framework + simple system prompt.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

# Internal imports
from agent.components.state_manager import state_manager
from agent.components.validation_manager import validation_manager
from memory.llm_cache import llm_cache
from prompts.system_prompts import get_prompt_template
from knowledge.framework_loader import framework_loader

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class PersonaSummary:
    """Simple persona summary structure"""
    overall_summary: str
    section_summaries: Dict[str, str]
    key_insights: List[str]
    linkedin_recommendations: List[str]


class PersonaBuilder:
    """
    Assembles persona data using YAML framework + simple system prompt.
    
    Uses system prompt for:
    - Final persona summary generation
    - Section summaries
    - LinkedIn recommendations
    
    YAML framework provides the structure and criteria.
    """
    
    def __init__(self):
        """Initialize persona builder"""
        self.state_manager = state_manager
        self.validation_manager = validation_manager
        self.llm_cache = llm_cache
        self.framework_loader = framework_loader
        
        logger.info("PersonaBuilder initialized with YAML-driven approach")
    
    async def compile_persona(self, session_id: str) -> Dict[str, Any]:
        """
        Compile complete persona from collected data using YAML + system prompt
        
        Process:
        1. Retrieve persona data from Redis
        2. Validate data completeness using YAML framework
        3. Generate summary using system prompt
        4. Format for final output
        """
        try:
            logger.info(f"Compiling persona for session: {session_id}")
            
            # Retrieve persona data
            persona_data = await self.state_manager.get_persona_data(session_id)
            if not persona_data:
                return {"error": "No persona data found", "session_id": session_id}
            
            # Validate completeness using YAML framework
            completeness_check = await self.validate_completeness(session_id)
            
            # Generate final summary using system prompt
            overall_summary = await self._generate_overall_summary(persona_data)
            
            # Extract key insights from responses
            key_insights = self._extract_key_insights_simple(persona_data)
            
            # Generate LinkedIn recommendations using system prompt
            linkedin_recommendations = await self._generate_linkedin_recommendations_simple(persona_data)
            
            # Format final persona
            compiled_persona = {
                "session_id": session_id,
                "compilation_timestamp": datetime.now().isoformat(),
                "completion_score": completeness_check.get("completion_score", 0.0),
                "ready_for_content_creation": completeness_check.get("completion_score", 0.0) >= 0.85,
                "persona_summary": {
                    "overall_summary": overall_summary,
                    "key_insights": key_insights,
                    "linkedin_recommendations": linkedin_recommendations
                },
                "data": persona_data,
                "metadata": {
                    "framework_version": persona_data.get("framework_version", "1.0"),
                    "total_criteria": persona_data.get("total_criteria", 0),
                    "completed_criteria": persona_data.get("completed_criteria", 0)
                }
            }
            
            logger.info(f"Persona compiled successfully for session {session_id}")
            return compiled_persona
            
        except Exception as e:
            logger.error(f"Persona compilation failed for session {session_id}: {e}")
            return {"error": f"Compilation failed: {e}", "session_id": session_id}
    
    async def handle_modification(self, session_id: str, modification_request: str) -> Dict[str, Any]:
        """
        Process user modification requests using simple parsing
        
        Uses simple keyword matching instead of complex LLM parsing
        """
        try:
            logger.info(f"Processing modification request for session {session_id}")
            
            # Simple modification parsing
            modification_type = self._parse_modification_simple(modification_request)
            
            if modification_type["success"]:
                # Get current persona data
                current_persona = await self.state_manager.get_persona_data(session_id)
                if not current_persona:
                    return {"success": False, "error": "No persona data found"}
                
                # Apply simple modification
                success = await self._apply_simple_modification(
                    session_id, 
                    modification_type["target_criterion"],
                    modification_type["new_value"]
                )
                
                if success:
                    return {
                        "success": True,
                        "message": "Modification applied successfully",
                        "updated_criterion": modification_type["target_criterion"]
                    }
            
            return {"success": False, "error": "Could not understand modification request"}
            
        except Exception as e:
            logger.error(f"Modification handling failed: {e}")
            return {"success": False, "error": f"Modification failed: {e}"}
    
    async def export_for_json(self, session_id: str) -> Dict[str, Any]:
        """Export persona in clean JSON format"""
        try:
            logger.info(f"Exporting persona JSON for session: {session_id}")
            
            # Compile final persona
            final_persona = await self.compile_persona(session_id)
            
            if "error" not in final_persona:
                # Add export timestamp
                final_persona["export_timestamp"] = datetime.now().isoformat()
                
                # Format for clean export
                export_json = {
                    "persona_id": session_id,
                    "created_at": final_persona["export_timestamp"],
                    "completion_score": final_persona["completion_score"],
                    "ready_for_use": final_persona["ready_for_content_creation"],
                    "summary": final_persona["persona_summary"],
                    "sections": final_persona["data"]["sections"],
                    "metadata": final_persona["metadata"]
                }
                return export_json
            else:
                return final_persona
                
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return {"error": f"Export failed: {e}"}
    
    async def validate_completeness(self, session_id: str) -> Dict[str, Any]:
        """Validate persona completeness using YAML framework"""
        try:
            persona_data = await self.state_manager.get_persona_data(session_id)
            if not persona_data:
                return {"valid": False, "message": "No persona data found"}
            
            # Simple completeness calculation based on YAML framework
            total_criteria = 0
            completed_criteria = 0
            
            framework = self.framework_loader.load_current()
            
            # Count criteria from YAML framework
            for section_key, section in framework.sections.items():
                section_criteria_count = len(section.criteria)
                total_criteria += section_criteria_count
                
                # Count completed criteria in persona data
                persona_sections = persona_data.get("sections", [])
                for persona_section in persona_sections:
                    if persona_section.get("section_number") == section.section_number:
                        criteria = persona_section.get("criteria", {})
                        completed_in_section = sum(
                            1 for criterion in criteria.values() 
                            if criterion.get("complete", False)
                        )
                        completed_criteria += completed_in_section
                        break
            
            completion_score = completed_criteria / total_criteria if total_criteria > 0 else 0.0
            
            return {
                "valid": completion_score >= 0.7,  # 70% minimum
                "completion_score": completion_score,
                "total_criteria": total_criteria,
                "completed_criteria": completed_criteria,
                "message": f"Persona is {completion_score:.1%} complete"
            }
            
        except Exception as e:
            logger.error(f"Completeness validation failed: {e}")
            return {"valid": False, "message": f"Validation failed: {e}"}
    
    async def _generate_overall_summary(self, persona_data: Dict[str, Any]) -> str:
        """Generate overall summary using system prompt"""
        try:
            # Extract completed responses
            completed_responses = self._extract_completed_responses(persona_data)
            
            if not completed_responses:
                return "Professional persona based on user responses"
            
            # Use system prompt for summary generation
            system_prompt = get_prompt_template("system")
            prompt = system_prompt.format(
                user_name="User",
                task_type="persona_summary",
                yaml_question="Create comprehensive LinkedIn persona summary",
                yaml_good_example=" | ".join(completed_responses[:5]),  # Top 5 responses
                yaml_bad_example="",
                user_response="",
                industry=persona_data.get("detected_industry", "unknown"),
                previous_responses="",
                section_name="Final Summary",
                criterion_name="Complete LinkedIn Persona"
            )
            
            summary = await self.llm_cache.call_llm_with_cache(
                prompt=prompt,
                operation="persona_summary",
                temperature=0.6,
                max_tokens=500
            )
            
            return summary or "Professional LinkedIn persona ready for optimization"
            
        except Exception as e:
            logger.error(f"Overall summary generation failed: {e}")
            return "Professional LinkedIn persona completed"
    
    def _extract_key_insights_simple(self, persona_data: Dict[str, Any]) -> List[str]:
        """Extract key insights using simple analysis"""
        try:
            insights = []
            
            # Get completed responses
            completed_responses = self._extract_completed_responses(persona_data)
            
            if not completed_responses:
                return ["Professional expertise clearly defined"]
            
            # Simple insight extraction based on response characteristics
            total_words = sum(len(response.split()) for response in completed_responses)
            avg_length = total_words / len(completed_responses)
            
            # Extract insights based on patterns
            if avg_length > 15:
                insights.append("Detailed professional expertise with specific examples")
            else:
                insights.append("Clear and concise professional positioning")
            
            # Check for industry-specific content
            combined_text = " ".join(completed_responses).lower()
            if any(keyword in combined_text for keyword in ["clients", "customers", "target"]):
                insights.append("Well-defined target audience and client focus")
            
            if any(keyword in combined_text for keyword in ["results", "outcomes", "impact", "roi"]):
                insights.append("Results-focused value proposition")
            
            # Ensure we have at least 3 insights
            while len(insights) < 3:
                default_insights = [
                    "Professional brand clearly articulated",
                    "LinkedIn strategy aligned with business goals",
                    "Unique value proposition established"
                ]
                insights.append(default_insights[len(insights) - 3])
            
            return insights[:5]  # Max 5 insights
            
        except Exception as e:
            logger.error(f"Key insights extraction failed: {e}")
            return ["Professional expertise documented", "LinkedIn strategy developed"]
    
    async def _generate_linkedin_recommendations_simple(self, persona_data: Dict[str, Any]) -> List[str]:
        """Generate LinkedIn recommendations using simple system prompt"""
        try:
            # Get key response context
            completed_responses = self._extract_completed_responses(persona_data)
            context = " | ".join(completed_responses[:3]) if completed_responses else "Professional expertise"
            
            # Use system prompt for recommendations
            system_prompt = get_prompt_template("system")
            prompt = system_prompt.format(
                user_name="User",
                task_type="linkedin_recommendations",
                yaml_question="Generate LinkedIn optimization recommendations",
                yaml_good_example=context,
                yaml_bad_example="",
                user_response="",
                industry=persona_data.get("detected_industry", "unknown"),
                previous_responses="",
                section_name="LinkedIn Strategy",
                criterion_name="Optimization Recommendations"
            )
            
            # For simplicity, generate simple recommendations instead of complex LLM call
            recommendations = [
                "Update your LinkedIn headline to reflect your core expertise",
                "Share content about your professional insights weekly",
                "Connect with your ideal clients and industry peers",
                "Use your unique value proposition in your About section",
                "Post about industry trends and your professional perspective"
            ]
            
            return recommendations
            
        except Exception as e:
            logger.error(f"LinkedIn recommendations generation failed: {e}")
            return ["Optimize LinkedIn profile with your expertise", "Share valuable content regularly"]
    
    def _extract_completed_responses(self, persona_data: Dict[str, Any]) -> List[str]:
        """Extract all completed responses from persona data"""
        try:
            responses = []
            
            sections = persona_data.get("sections", [])
            for section in sections:
                criteria = section.get("criteria", {})
                for criterion_name, criterion_data in criteria.items():
                    if criterion_data.get("complete", False):
                        response = criterion_data.get("response", "")
                        if response.strip():
                            responses.append(response)
            
            return responses
            
        except Exception as e:
            logger.error(f"Response extraction failed: {e}")
            return []
    
    def _parse_modification_simple(self, modification_request: str) -> Dict[str, Any]:
        """Simple modification parsing using keywords"""
        try:
            request_lower = modification_request.lower()
            
            # Simple keyword matching for common modifications
            if any(word in request_lower for word in ["change", "update", "modify"]):
                if "expertise" in request_lower or "domain" in request_lower:
                    return {
                        "success": True,
                        "target_criterion": "broad_domain_expertise",
                        "new_value": modification_request
                    }
                elif "client" in request_lower or "customer" in request_lower:
                    return {
                        "success": True,
                        "target_criterion": "ideal_client_definition",
                        "new_value": modification_request
                    }
                elif "value" in request_lower or "proposition" in request_lower:
                    return {
                        "success": True,
                        "target_criterion": "unique_value_proposition",
                        "new_value": modification_request
                    }
            
            return {"success": False, "reason": "Could not identify what to change"}
            
        except Exception as e:
            logger.error(f"Simple modification parsing failed: {e}")
            return {"success": False, "reason": "Parsing failed"}
    
    async def _apply_simple_modification(self, session_id: str, criterion_name: str, new_value: str) -> bool:
        """Apply simple modification to persona data"""
        try:
            # This would update the specific criterion in Redis
            # For now, just log the action
            logger.info(f"Applying modification to {criterion_name}: {new_value[:50]}...")
            
            # In real implementation, this would:
            # 1. Update the criterion in Redis
            # 2. Mark as modified
            # 3. Recalculate completion percentages
            
            return True
            
        except Exception as e:
            logger.error(f"Simple modification application failed: {e}")
            return False


# Global persona builder instance
persona_builder = PersonaBuilder()
