"""
Information Extraction Tool for extracting framework information from conversations.
"""

import logging
import yaml
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import re

logger = logging.getLogger(__name__)


class InformationExtractionTool:
    """Tool for extracting framework information from user responses."""
    
    def __init__(self, llm_tool=None):
        """Initialize the information extraction tool."""
        self.llm_tool = llm_tool
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
    
    async def extract_information(self, user_response: str, 
                                session_state: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Extract framework information from user response.
        
        Args:
            user_response: User's conversational response
            session_state: Current session state for context
            
        Returns:
            Dictionary of extracted information with confidence scores
        """
        if not self.framework_criteria:
            return {"error": "Framework criteria not loaded"}
            
        # Create extraction prompt
        extraction_prompt = self._create_extraction_prompt(user_response, session_state)
        
        try:
            # Use LLM to extract information
            logger.info(f"Extracting information from: '{user_response[:100]}...'")
            
            response = await self.llm_tool.generate_for_agent(
                "information_extractor",
                extraction_prompt,
                temperature=0.1,
                max_tokens=1000
            )
            
            # Parse the response
            extracted_info = self._parse_extraction_response(response)
            
            # Validate against criteria
            validated_info = self._validate_extractions(extracted_info)
            
            logger.info(f"Extracted {len(validated_info)} information points")
            return validated_info
            
        except Exception as e:
            logger.error(f"Information extraction failed: {e}")
            return {"error": str(e)}
    
    def _create_extraction_prompt(self, user_response: str, 
                                session_state: Dict[str, Any] = None) -> str:
        """Create LLM prompt for information extraction."""
        
        # Get framework sections for context
        sections = self.framework_criteria.get("framework_sections", {})
        
        # Create criteria summary
        criteria_summary = []
        for section_name, section_data in sections.items():
            criteria_summary.append(f"\n{section_data['section_name']}:")
            for criteria_key, criteria_info in section_data['criteria'].items():
                criteria_summary.append(f"  - {criteria_key}: {criteria_info['description']}")
        
        criteria_text = "\n".join(criteria_summary)
        
        # Add current session state context if available
        context_text = ""
        if session_state and session_state.get("extracted_information"):
            context_text = f"\nCURRENT SESSION STATE:\n{session_state['extracted_information']}"
        
        prompt = f"""
Analyze the following user response and extract any information that matches the framework criteria below.

USER RESPONSE:
"{user_response}"

FRAMEWORK CRITERIA:
{criteria_text}

{context_text}

INSTRUCTIONS:
1. Identify ALL information in the user response that matches any framework criteria
2. For each match, provide:
   - framework_section: The section name (e.g., "core_expertise")
   - criteria_key: The specific criteria (e.g., "broad_expertise") 
   - extracted_value: The specific information from the response
   - confidence_score: 0.0 to 1.0 based on how well it matches the criteria
   - reasoning: Brief explanation of why this extraction was made

3. Look for multiple extractions - one response might contain information for several criteria
4. Only extract information that is explicitly stated or clearly implied
5. Don't make assumptions or fill in gaps

RESPOND WITH VALID JSON:
{{
  "extractions": [
    {{
      "framework_section": "section_name",
      "criteria_key": "criteria_key",
      "extracted_value": "specific information from response",
      "confidence_score": 0.8,
      "reasoning": "explanation of extraction"
    }}
  ]
}}

RESPOND ONLY WITH THE JSON STRUCTURE ABOVE.
"""
        
        return prompt.strip()
    
    def _parse_extraction_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into structured extractions."""
        try:
            import json
            
            # Clean the response
            response = response.strip()
            
            # Try to extract JSON if wrapped in other text
            if not response.startswith('{'):
                # Look for JSON block
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    response = json_match.group(0)
            
            # Parse JSON
            parsed = json.loads(response)
            
            # Extract extractions list
            extractions = parsed.get("extractions", [])
            
            logger.info(f"Parsed {len(extractions)} extractions from response")
            return extractions
            
        except Exception as e:
            logger.error(f"Failed to parse extraction response: {e}")
            logger.error(f"Response was: {response}")
            return []
    
    def _validate_extractions(self, extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Validate extractions against framework criteria."""
        validated = {
            "extractions": [],
            "validation_summary": {
                "total_extractions": len(extractions),
                "valid_extractions": 0,
                "invalid_extractions": 0,
                "sections_updated": set()
            }
        }
        
        sections = self.framework_criteria.get("framework_sections", {})
        
        for extraction in extractions:
            # Validate required fields
            if not all(key in extraction for key in ["framework_section", "criteria_key", "extracted_value"]):
                logger.warning(f"Invalid extraction missing required fields: {extraction}")
                validated["validation_summary"]["invalid_extractions"] += 1
                continue
            
            # Validate section and criteria exist
            section_name = extraction["framework_section"]
            criteria_key = extraction["criteria_key"]
            
            if section_name not in sections:
                logger.warning(f"Unknown framework section: {section_name}")
                validated["validation_summary"]["invalid_extractions"] += 1
                continue
                
            if criteria_key not in sections[section_name]["criteria"]:
                logger.warning(f"Unknown criteria key: {criteria_key} in section {section_name}")
                validated["validation_summary"]["invalid_extractions"] += 1
                continue
            
            # Get criteria threshold
            criteria_info = sections[section_name]["criteria"][criteria_key]
            threshold = criteria_info.get("confidence_threshold", 0.7)
            
            # Validate confidence score
            confidence = extraction.get("confidence_score", 0.0)
            if confidence < threshold:
                logger.info(f"Extraction below threshold ({confidence} < {threshold}): {extraction}")
                extraction["needs_follow_up"] = True
            
            # Mark as valid
            validated["extractions"].append(extraction)
            validated["validation_summary"]["valid_extractions"] += 1
            validated["validation_summary"]["sections_updated"].add(section_name)
        
        # Convert set to list for JSON serialization
        validated["validation_summary"]["sections_updated"] = list(
            validated["validation_summary"]["sections_updated"]
        )
        
        return validated
    
    def get_missing_criteria(self, current_state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get list of missing or insufficient criteria."""
        missing = []
        
        sections = self.framework_criteria.get("framework_sections", {})
        thresholds = self.framework_criteria.get("assessment_thresholds", {})
        min_confidence = thresholds.get("sufficient_confidence", 0.7)
        
        for section_name, section_data in sections.items():
            for criteria_key, criteria_info in section_data["criteria"].items():
                
                # Check if this criteria is in current state
                current_value = current_state.get("extracted_information", {}).get(section_name, {}).get(criteria_key)
                
                if not current_value:
                    missing.append({
                        "framework_section": section_name,
                        "criteria_key": criteria_key,
                        "description": criteria_info["description"],
                        "conversation_starters": criteria_info.get("conversation_starters", []),
                        "priority": "missing"
                    })
                elif current_value.get("confidence", 0.0) < min_confidence:
                    missing.append({
                        "framework_section": section_name,
                        "criteria_key": criteria_key,
                        "description": criteria_info["description"],
                        "conversation_starters": criteria_info.get("conversation_starters", []),
                        "priority": "insufficient",
                        "current_confidence": current_value.get("confidence", 0.0)
                    })
        
        # Sort by priority (missing first, then insufficient)
        missing.sort(key=lambda x: (x["priority"] == "insufficient", x["framework_section"], x["criteria_key"]))
        
        return missing
    
    def get_completion_status(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """Get overall completion status of framework."""
        sections = self.framework_criteria.get("framework_sections", {})
        thresholds = self.framework_criteria.get("assessment_thresholds", {})
        
        status = {
            "overall_completion": 0.0,
            "section_completion": {},
            "total_criteria": 0,
            "completed_criteria": 0,
            "missing_criteria": 0,
            "insufficient_criteria": 0
        }
        
        extracted_info = current_state.get("extracted_information", {})
        
        for section_name, section_data in sections.items():
            section_criteria = section_data["criteria"]
            section_total = len(section_criteria)
            section_completed = 0
            section_confidence_sum = 0.0
            
            for criteria_key, criteria_info in section_criteria.items():
                status["total_criteria"] += 1
                
                current_value = extracted_info.get(section_name, {}).get(criteria_key)
                threshold = criteria_info.get("confidence_threshold", 0.7)
                
                if current_value:
                    confidence = current_value.get("confidence", 0.0)
                    section_confidence_sum += confidence
                    
                    if confidence >= threshold:
                        section_completed += 1
                        status["completed_criteria"] += 1
                    else:
                        status["insufficient_criteria"] += 1
                else:
                    status["missing_criteria"] += 1
            
            # Calculate section completion
            if section_total > 0:
                section_avg_confidence = section_confidence_sum / section_total
                status["section_completion"][section_name] = {
                    "completion_percentage": (section_completed / section_total) * 100,
                    "average_confidence": section_avg_confidence,
                    "completed_criteria": section_completed,
                    "total_criteria": section_total
                }
        
        # Calculate overall completion
        if status["total_criteria"] > 0:
            status["overall_completion"] = (status["completed_criteria"] / status["total_criteria"]) * 100
        
        return status
