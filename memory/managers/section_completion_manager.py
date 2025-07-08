"""
Section Completion Manager - Tracks framework progress and manages section transitions.
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import yaml
from pathlib import Path

from database.models import SectionProgress, FrameworkExtraction, ConversationState
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SectionCompletionManager:
    """
    Manages section completion tracking and cross-section data storage.
    Integrates with LLM to provide intelligent context about what's missing.
    """
    
    def __init__(self, database=None):
        self.database = database
        self.framework_criteria = self._load_framework_criteria()
        self.section_mapping = self._build_section_mapping()
        
    def _load_framework_criteria(self) -> Dict[str, Any]:
        """Load framework criteria from YAML file."""
        try:
            criteria_path = Path(__file__).parent.parent.parent / "knowledge" / "framework_criteria.yaml"
            with open(criteria_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load framework criteria: {e}")
            return {}
    
    def _build_section_mapping(self) -> Dict[int, Dict[str, Any]]:
        """Build mapping of section numbers to their criteria."""
        mapping = {}
        sections = self.framework_criteria.get('framework_sections', {})
        
        for i, (section_name, section_data) in enumerate(sections.items(), 1):
            mapping[i] = {
                'name': section_name,
                'criteria': list(section_data.get('criteria', {}).keys()),
                'total_criteria': len(section_data.get('criteria', {}))
            }
        
        return mapping
    
    async def get_conversation_state(self, session_id: str) -> ConversationState:
        """Get current conversation state with section progress, loading existing extractions."""
        # Build fresh state
        state = ConversationState(session_id=session_id)
        
        # Initialize section progress
        for section_num, section_info in self.section_mapping.items():
            state.section_progress[section_num] = SectionProgress(
                session_id=session_id,
                section_number=section_num,
                section_name=section_info['name'],
                criteria_missing=section_info['criteria'].copy()
            )
        
        # Load existing extractions from database
        if self.database:
            try:
                result = self.database.client.table('framework_extractions').select('*').eq(
                    'session_id', session_id
                ).execute()
                
                if result.data:
                    for extraction_data in result.data:
                        # Find the section for this extraction
                        section_name = extraction_data['framework_section']
                        section_num = self._get_section_number_by_name(section_name)
                        
                        if section_num and section_num in state.section_progress:
                            section = state.section_progress[section_num]
                            criteria_key = extraction_data['criteria_key']
                            
                            # Move from missing to completed
                            if criteria_key in section.criteria_missing:
                                section.criteria_missing.remove(criteria_key)
                                if criteria_key not in section.criteria_completed:
                                    section.criteria_completed.append(criteria_key)
                    
                    # Recalculate completion percentages
                    self._recalculate_progress(state)
                    
            except Exception as e:
                logger.warning(f"Could not load extractions from database: {e}")
        
        return state
    
    def _recalculate_progress(self, state: ConversationState):
        """Recalculate completion percentages for all sections."""
        for section_num, section in state.section_progress.items():
            total_criteria = len(section.criteria_completed) + len(section.criteria_missing)
            if total_criteria > 0:
                section.completion_percentage = (len(section.criteria_completed) / total_criteria) * 100
                section.is_complete = section.completion_percentage >= 80.0
            else:
                section.completion_percentage = 0.0
                section.is_complete = False
        
        # Update overall completion
        total_completed = sum(len(s.criteria_completed) for s in state.section_progress.values())
        total_criteria = sum(len(s.criteria_completed) + len(s.criteria_missing) for s in state.section_progress.values())
        
        if total_criteria > 0:
            overall_completion = (total_completed / total_criteria) * 100
        else:
            overall_completion = 0.0
        
        return overall_completion

    def _get_section_number_by_name(self, section_name: str) -> Optional[int]:
        """Get section number by section name."""
        for section_num, section_info in self.section_mapping.items():
            if section_info['name'] == section_name:
                return section_num
        return None

    async def update_extractions(self, session_id: str, extractions: List[FrameworkExtraction]) -> ConversationState:
        """Update framework extractions and recalculate section progress."""
        state = await self.get_conversation_state(session_id)
        
        # Process each extraction
        for extraction in extractions:
            section_num = self._get_section_number_by_name(extraction.framework_section)
            if section_num and section_num in state.section_progress:
                section = state.section_progress[section_num]
                
                # Update criteria completion
                if extraction.criteria_key in section.criteria_missing:
                    section.criteria_missing.remove(extraction.criteria_key)
                
                if extraction.criteria_key not in section.criteria_completed:
                    section.criteria_completed.append(extraction.criteria_key)
                
                # Update completion percentage
                total_criteria = self.section_mapping[section_num]['total_criteria']
                section.completion_percentage = len(section.criteria_completed) / total_criteria * 100
                section.is_complete = len(section.criteria_missing) == 0
                section.updated_at = datetime.utcnow()
            
            # Store extraction in database
            if self.database:
                await self._store_extraction(extraction)
        
        # Update current section if current one is complete
        current_section = state.current_section
        if (current_section in state.section_progress and 
            state.section_progress[current_section].is_complete and
            current_section < state.total_sections):
            state.current_section += 1
        
        # Save updated state
        await self._save_conversation_state(state)
        
        return state
    
    def _get_section_number_by_name(self, section_name: str) -> Optional[int]:
        """Get section number by section name."""
        for num, info in self.section_mapping.items():
            if info['name'] == section_name:
                return num
        return None
    
    async def _store_extraction(self, extraction: FrameworkExtraction):
        """Store extraction in database with proper duplicate handling."""
        if not self.database:
            return
            
        try:
            # Check if extraction already exists to prevent duplicates
            existing = self.database.client.table('framework_extractions').select('id').eq(
                'session_id', extraction.session_id
            ).eq(
                'framework_section', extraction.framework_section
            ).eq(
                'criteria_key', extraction.criteria_key
            ).execute()
            
            # Only insert if it doesn't exist
            if not existing.data:
                extraction_data = {
                    'session_id': extraction.session_id,
                    'framework_section': extraction.framework_section,
                    'criteria_key': extraction.criteria_key,
                    'extracted_value': extraction.extracted_value,
                    'confidence_score': extraction.confidence_score,
                    'reasoning': extraction.reasoning,
                    'extraction_method': extraction.extraction_method,
                    'extracted_at': extraction.extracted_at.isoformat()
                }
                
                result = self.database.client.table('framework_extractions').insert(extraction_data).execute()
                logger.debug(f"Stored new extraction: {extraction.criteria_key}")
            else:
                logger.debug(f"Extraction already exists: {extraction.criteria_key}")
            
        except Exception as e:
            logger.error(f"Failed to store extraction: {e}")
    
    async def _save_conversation_state(self, state: ConversationState):
        """Save conversation state to database."""
        # For now, we'll store this in session metadata
        # In future, could have dedicated conversation_states table
        if self.database:
            try:
                # Update session with framework completion percentage
                overall_completion = self._calculate_overall_completion(state)
                session_update = {
                    'framework_completion_percentage': overall_completion,
                    'total_information_extracted': sum(
                        len(s.criteria_completed) for s in state.section_progress.values()
                    ),
                    'updated_at': datetime.utcnow().isoformat()
                }
                
                result = self.database.client.table('persona_sessions').update(session_update).eq('id', state.session_id).execute()
                
            except Exception as e:
                logger.error(f"Failed to save conversation state: {e}")
    
    def _calculate_overall_completion(self, state: ConversationState) -> float:
        """Calculate overall completion percentage across all sections."""
        if not state.section_progress:
            return 0.0
        
        total_criteria = sum(info['total_criteria'] for info in self.section_mapping.values())
        completed_criteria = sum(len(s.criteria_completed) for s in state.section_progress.values())
        
        return (completed_criteria / total_criteria) * 100 if total_criteria > 0 else 0.0
    
    def build_context_for_llm(self, state: ConversationState) -> str:
        """Build structured context string for LLM prompt."""
        current_section = state.section_progress.get(state.current_section)
        if not current_section:
            return "No section data available."
        
        context_parts = []
        
        # Current section status
        context_parts.append(f"CURRENT SECTION: {current_section.section_name} ({len(current_section.criteria_completed)}/{len(current_section.criteria_completed) + len(current_section.criteria_missing)} criteria completed)")
        
        # Completed criteria
        if current_section.criteria_completed:
            context_parts.append("COMPLETED CRITERIA:")
            for criteria in current_section.criteria_completed:
                context_parts.append(f"✅ {criteria}")
        
        # Missing criteria
        if current_section.criteria_missing:
            context_parts.append("MISSING CRITERIA:")
            for criteria in current_section.criteria_missing:
                context_parts.append(f"❌ {criteria}")
        
        # Cross-section data
        if current_section.cross_section_data:
            context_parts.append("CROSS-SECTION DATA CAPTURED:")
            for key, value in current_section.cross_section_data.items():
                context_parts.append(f"- {key}: {value}")
        
        # Instructions
        context_parts.append(f"\nINSTRUCTIONS:")
        context_parts.append(f"- You MUST complete Section {state.current_section} before moving to Section {state.current_section + 1}")
        context_parts.append(f"- Ask natural, conversational questions to get missing criteria")
        context_parts.append(f"- Reference previous answers when relevant")
        context_parts.append(f"- When section is 100% complete, move to next section")
        context_parts.append(f"- Be direct but conversational, minimal fluff")
        
        return "\n".join(context_parts)
    
    async def check_section_completion(self, session_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Check if current section is complete and return status."""
        state = await self.get_conversation_state(session_id)
        current_section = state.section_progress.get(state.current_section)
        
        if not current_section:
            return False, {"error": "No current section found"}
        
        is_complete = current_section.is_complete
        
        status = {
            "section_complete": is_complete,
            "section_name": current_section.section_name,
            "completion_percentage": current_section.completion_percentage,
            "missing_criteria": current_section.criteria_missing,
            "next_section": state.current_section + 1 if is_complete and state.current_section < state.total_sections else None,
            "overall_completion": self._calculate_overall_completion(state)
        }
        
        return is_complete, status
