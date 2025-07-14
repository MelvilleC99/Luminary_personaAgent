from typing import Dict, Any, List, Optional
from datetime import datetime
from data.redis.schemas import (
    PersonaData, SectionProgress, CriterionData as PersonaCriterionData, 
    EvaluationResult, CrossSectionMatch
)
from data.redis.redis_utils import redis_manager, save_persona, get_persona
from data.supabase.supabase_utils import supabase_manager
from knowledge.framework_loader import framework_loader
from orchestrator.config import settings
import logging
logger = logging.getLogger(__name__)


class StateManager:
    """
    Handles Redis state management and persona data updates
    """
    
    def __init__(self):
        self.completion_threshold = settings.section_completion_threshold
        self.framework = framework_loader.load_current()
    
    async def initialize_persona_data(self, session_id: str) -> PersonaData:
        """Initialize empty persona data structure"""
        try:
            framework = framework_loader.load_current()
            sections = []
            
            # Create empty sections based on framework
            for section_key, section_data in framework.sections.items():
                section_progress = SectionProgress(
                    section_number=section_data.section_number,
                    section_name=section_data.name,
                    completion_percentage=0.0,
                    criteria={},
                    started_at=None,
                    completed_at=None
                )
                
                # Initialize empty criteria
                for criterion_name, criterion in section_data.criteria.items():
                    section_progress.criteria[criterion_name] = PersonaCriterionData(
                        name=criterion_name,
                        response="",
                        confidence=0.0,
                        quality_score=0,
                        complete=False,
                        attempts=0,
                        timestamp=None,
                        cross_section_source=False
                    )
                
                sections.append(section_progress)
            
            persona_data = PersonaData(
                sections=sections,
                overall_completion=0.0,
                total_criteria=sum(len(section.criteria) for section in sections),
                completed_criteria=0,
                last_updated=datetime.now()
            )
            
            # Save to Redis
            success = await save_persona(session_id, persona_data)
            if success:
                logger.info("Persona data initialized", session_id=session_id)
            
            return persona_data
            
        except Exception as e:
            logger.error(f"Persona data initialization failed: {e}")
            return PersonaData()
    
    async def update_persona_criterion(self, session_id: str, section_number: int,
                                     criterion_name: str, evaluation: EvaluationResult,
                                     user_response: str, cross_section_source: bool = False) -> bool:
        """Update specific criterion in persona data"""
        try:
            # Get current persona data
            persona_data = await get_persona(session_id)
            if not persona_data:
                persona_data = await self.initialize_persona_data(session_id)
            
            # Find target section
            target_section = None
            for section in persona_data.sections:
                if section.section_number == section_number:
                    target_section = section
                    break
            
            if not target_section:
                logger.error(f"Section {section_number} not found - session_id: {session_id}")
                return False
            
            # Update criterion
            if criterion_name in target_section.criteria:
                criterion_data = target_section.criteria[criterion_name]
                
                # Update criterion data
                criterion_data.response = user_response
                criterion_data.confidence = evaluation.confidence
                criterion_data.quality_score = evaluation.quality_score
                criterion_data.complete = evaluation.quality_score >= 6 and evaluation.confidence >= 0.6
                criterion_data.attempts += 1 if not cross_section_source else 0
                criterion_data.timestamp = datetime.now()
                criterion_data.cross_section_source = cross_section_source
                
                logger.info("Criterion updated",
                          session_id=session_id,
                          criterion=criterion_name,
                          quality_score=evaluation.quality_score,
                          complete=criterion_data.complete)
                
                logger.info(f"Response evaluated for {criterion_name}",
                          session_id=session_id,
                          quality_score=evaluation.quality_score,
                          confidence=evaluation.confidence)
            else:
                logger.warning(f"Criterion {criterion_name} not found in section {section_number}")
                return False
            
            # Recalculate section completion
            await self._recalculate_section_completion(target_section)
            
            # Recalculate overall completion
            await self._recalculate_overall_completion(persona_data)
            
            # Mark section as started if first criterion
            if not target_section.started_at:
                target_section.started_at = datetime.now()
            
            # Check if section is complete
            if target_section.completion_percentage >= self.completion_threshold:
                if not target_section.completed_at:
                    target_section.completed_at = datetime.now()
                    logger.info(f"Section {section_number} completed",
                              session_id=session_id,
                              completion_percentage=target_section.completion_percentage)
            
            # Update timestamp
            persona_data.last_updated = datetime.now()
            
            # Save updated persona data
            success = await save_persona(session_id, persona_data)
            
            # Trigger Supabase sync if section is complete
            if target_section.completion_percentage >= self.completion_threshold:
                await self._trigger_supabase_sync(session_id, persona_data)
            
            return success
            
        except Exception as e:
            logger.error(f"Criterion update failed: {e} - session_id: {session_id}")
            return False
    
    async def update_cross_section_matches(self, session_id: str, 
                                         matches: List[CrossSectionMatch]) -> int:
        """Update multiple criteria from cross-section matches"""
        try:
            updated_count = 0
            
            for match in matches:
                success = await self.update_persona_criterion(
                    session_id=session_id,
                    section_number=match.section_number,
                    criterion_name=match.criterion_name,
                    evaluation=match.evaluation_result,
                    user_response=match.evaluation_result.extracted_info,
                    cross_section_source=True
                )
                
                if success:
                    updated_count += 1
                    logger.info("Cross-section match updated",
                              session_id=session_id,
                              criterion=match.criterion_name,
                              section=match.section_number)
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Cross-section updates failed: {e}")
            return 0
    
    async def _recalculate_section_completion(self, section: SectionProgress):
        """Recalculate completion percentage for a section"""
        try:
            if not section.criteria:
                section.completion_percentage = 0.0
                return
            
            completed_count = sum(1 for criterion in section.criteria.values() if criterion.complete)
            total_count = len(section.criteria)
            
            section.completion_percentage = completed_count / total_count if total_count > 0 else 0.0
            
        except Exception as e:
            logger.error(f"Section completion calculation failed: {e}")
            section.completion_percentage = 0.0
    
    async def _recalculate_overall_completion(self, persona_data: PersonaData):
        """Recalculate overall completion percentage"""
        try:
            if not persona_data.sections:
                persona_data.overall_completion = 0.0
                return
            
            # Calculate weighted average of section completions
            total_completion = sum(section.completion_percentage for section in persona_data.sections)
            persona_data.overall_completion = total_completion / len(persona_data.sections)
            
            # Update completed criteria count
            persona_data.completed_criteria = sum(
                sum(1 for criterion in section.criteria.values() if criterion.complete)
                for section in persona_data.sections
            )
            
        except Exception as e:
            logger.error(f"Overall completion calculation failed: {e}")
            persona_data.overall_completion = 0.0
    
    async def get_section_progress(self, session_id: str, section_number: int) -> Optional[SectionProgress]:
        """Get progress for specific section"""
        try:
            persona_data = await get_persona(session_id)
            if not persona_data:
                return None
            
            for section in persona_data.sections:
                if section.section_number == section_number:
                    return section
            
            return None
            
        except Exception as e:
            logger.error(f"Section progress retrieval failed: {e}")
            return None
    
    async def get_next_incomplete_criterion(self, session_id: str, 
                                          section_number: int) -> Optional[str]:
        """Get next incomplete criterion in section"""
        try:
            section = await self.get_section_progress(session_id, section_number)
            if not section:
                return None
            
            # Find first incomplete criterion
            for criterion_name, criterion in section.criteria.items():
                if not criterion.complete:
                    return criterion_name
            
            return None
            
        except Exception as e:
            logger.error(f"Next criterion lookup failed: {e}")
            return None
    
    async def get_incomplete_criteria(self, session_id: str, 
                                    section_number: int) -> List[str]:
        """Get all incomplete criteria in section"""
        try:
            section = await self.get_section_progress(session_id, section_number)
            if not section:
                return []
            
            incomplete = []
            for criterion_name, criterion in section.criteria.items():
                if not criterion.complete:
                    incomplete.append(criterion_name)
            
            return incomplete
            
        except Exception as e:
            logger.error(f"Incomplete criteria lookup failed: {e}")
            return []
    
    async def is_section_complete(self, session_id: str, section_number: int) -> bool:
        """Check if section meets completion threshold"""
        try:
            section = await self.get_section_progress(session_id, section_number)
            if not section:
                return False
            
            return section.completion_percentage >= self.completion_threshold
            
        except Exception as e:
            logger.error(f"Section completion check failed: {e}")
            return False
    
    async def get_overall_progress(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive progress information"""
        try:
            persona_data = await get_persona(session_id)
            if not persona_data:
                return {
                    "overall_completion": 0.0,
                    "section_progress": {},
                    "total_criteria": 0,
                    "completed_criteria": 0
                }
            
            section_progress = {}
            for section in persona_data.sections:
                section_progress[f"section_{section.section_number}"] = {
                    "name": section.section_name,
                    "completion_percentage": section.completion_percentage,
                    "started": section.started_at is not None,
                    "completed": section.completed_at is not None,
                    "criteria_count": len(section.criteria),
                    "completed_criteria": sum(1 for c in section.criteria.values() if c.complete)
                }
            
            return {
                "overall_completion": persona_data.overall_completion,
                "section_progress": section_progress,
                "total_criteria": persona_data.total_criteria,
                "completed_criteria": persona_data.completed_criteria,
                "last_updated": persona_data.last_updated.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Progress retrieval failed: {e}")
            return {"overall_completion": 0.0, "section_progress": {}}
    
    async def park_criterion(self, session_id: str, section_number: int, 
                           criterion_name: str, reason: str = "max_attempts") -> bool:
        """Park criterion for later review (after max follow-up attempts)"""
        try:
            # Store parked criterion info in temp data
            parked_data = {
                "section_number": section_number,
                "criterion_name": criterion_name,
                "reason": reason,
                "timestamp": datetime.now().isoformat()
            }
            
            success = await redis_manager.set_temp_data(
                session_id, 
                f"parked_criterion_{criterion_name}", 
                parked_data,
                ttl=86400  # 24 hours
            )
            
            if success:
                logger.info("Criterion parked", 
                          session_id=session_id,
                          criterion=criterion_name,
                          reason=reason)
            
            return success
            
        except Exception as e:
            logger.error(f"Criterion parking failed: {e}")
            return False
    
    async def get_parked_criteria(self, session_id: str) -> List[Dict[str, Any]]:
        """Get list of parked criteria for review"""
        try:
            # This would require a Redis pattern search
            # For now, return empty list (parked criteria handled in review phase)
            return []
            
        except Exception as e:
            logger.error(f"Parked criteria retrieval failed: {e}")
            return []
    
    async def _trigger_supabase_sync(self, session_id: str, persona_data: PersonaData):
        """Trigger sync to Supabase when section is complete"""
        try:
            # Get session info for user_id
            session_state = await redis_manager.get_session_data(session_id)
            if session_state:
                await supabase_manager.upsert_persona(
                    session_id=session_id,
                    persona_data=persona_data,
                    user_id=session_state.user_id,
                    industry=session_state.industry
                )
                logger.info("Persona data synced to Supabase", session_id=session_id)
            
        except Exception as e:
            logger.warning(f"Supabase sync failed (non-critical): {e}")
    
    async def backup_to_supabase(self, session_id: str) -> bool:
        """Manual backup of persona data to Supabase"""
        try:
            persona_data = await get_persona(session_id)
            session_state = await redis_manager.get_session_data(session_id)
            
            if persona_data and session_state:
                success = await supabase_manager.upsert_persona(
                    session_id=session_id,
                    persona_data=persona_data,
                    user_id=session_state.user_id,
                    industry=session_state.industry
                )
                
                if success:
                    logger.info("Manual backup completed", session_id=session_id)
                
                return success
            
            return False
            
        except Exception as e:
            logger.error(f"Manual backup failed: {e}")
            return False


# Global state manager instance
state_manager = StateManager()
