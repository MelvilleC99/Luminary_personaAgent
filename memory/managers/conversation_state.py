"""
Conversation State Manager for tracking persona building progress.
Manages section completion, criteria tracking, and conversation flow state.
"""

import logging
import json
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone
from enum import Enum

from database.models import ConversationState, SectionProgress

logger = logging.getLogger(__name__)


class ConversationStage(str, Enum):
    """Enumeration of conversation stages."""
    INITIAL_GREETING = "initial_greeting"
    WAITING_FOR_SECTION_CONFIRM = "waiting_for_section_confirm"
    SECTION_WORK = "section_work"
    SECTION_TRANSITION = "section_transition"
    RESUMING = "resuming"
    COMPLETED = "completed"


class ConversationStateManager:
    """
    Manages conversation state and framework progress tracking.
    Handles section completion, criteria tracking, and conversation flow.
    """
    
    def __init__(self, redis_context_manager=None, database=None, **kwargs):
        """
        Initialize conversation state manager.
        
        Args:
            redis_context_manager: Redis context manager for fast state access
            database: Database for persistent state storage
            **kwargs: Additional configuration options
        """
        self.redis_context = redis_context_manager
        self.database = database
        
        # Configuration
        self.framework_sections = kwargs.get("framework_sections", {})
        self.total_sections = len(self.framework_sections)
        
        # State cache
        self.state_cache = {}
        
        logger.info(f"Initialized ConversationStateManager with {self.total_sections} sections")
    
    async def get_conversation_state(self, session_id: str) -> ConversationState:
        """
        Get conversation state for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            ConversationState object
        """
        # Check cache first
        if session_id in self.state_cache:
            return self.state_cache[session_id]
        
        # Try to load from Redis
        state = await self._load_state_from_redis(session_id)
        if state:
            self.state_cache[session_id] = state
            return state
        
        # Try to load from database
        state = await self._load_state_from_database(session_id)
        if state:
            self.state_cache[session_id] = state
            return state
        
        # Create new state
        state = self._create_new_state(session_id)
        self.state_cache[session_id] = state
        return state
    
    async def _load_state_from_redis(self, session_id: str) -> Optional[ConversationState]:
        """Load conversation state from Redis."""
        if not self.redis_context or not self.redis_context._redis_connected:
            return None
        
        try:
            state_key = f"conversation_state:{session_id}"
            state_data = await self.redis_context.redis.hgetall(state_key)
            
            if not state_data:
                return None
            
            # Parse section progress
            section_progress = {}
            if state_data.get("section_progress"):
                section_progress_data = json.loads(state_data["section_progress"])
                for section_num, progress_data in section_progress_data.items():
                    section_progress[int(section_num)] = SectionProgress(**progress_data)
            
            # Create conversation state
            state = ConversationState(
                session_id=session_id,
                current_section=int(state_data.get("current_section", 1)),
                total_sections=int(state_data.get("total_sections", self.total_sections)),
                section_progress=section_progress,
                conversation_summary=state_data.get("conversation_summary", ""),
                recent_context=json.loads(state_data.get("recent_context", "[]")),
                token_count=int(state_data.get("token_count", 0)),
                conversation_stage=state_data.get("conversation_stage", "initial_greeting"),
                last_updated=datetime.fromisoformat(state_data["last_updated"]) if state_data.get("last_updated") else datetime.now(timezone.utc)
            )
            
            logger.debug(f"Loaded conversation state from Redis for session {session_id}")
            return state
            
        except Exception as e:
            logger.error(f"Failed to load state from Redis: {e}")
            return None
    
    async def _load_state_from_database(self, session_id: str) -> Optional[ConversationState]:
        """Load conversation state from database."""
        if not self.database:
            return None
        
        try:
            # This would be implemented based on your database schema
            # For now, return None and let it create a new state
            return None
            
        except Exception as e:
            logger.error(f"Failed to load state from database: {e}")
            return None
    
    def _create_new_state(self, session_id: str) -> ConversationState:
        """Create a new conversation state."""
        # Initialize section progress for all sections
        section_progress = {}
        for i, (section_key, section_data) in enumerate(self.framework_sections.items(), 1):
            section_progress[i] = SectionProgress(
                session_id=session_id,
                section_number=i,
                section_name=section_data.get("section_name", section_key),
                criteria_completed=[],
                criteria_missing=list(section_data.get("criteria", {}).keys()),
                completion_percentage=0.0,
                is_complete=False
            )
        
        state = ConversationState(
            session_id=session_id,
            current_section=1,
            total_sections=self.total_sections,
            section_progress=section_progress,
            conversation_summary="",
            recent_context=[],
            token_count=0,
            last_updated=datetime.now(timezone.utc)
        )
        
        # Set initial conversation stage
        state.conversation_stage = "initial_greeting"
        
        logger.debug(f"Created new conversation state for session {session_id} with stage: initial_greeting")
        return state
    
    async def update_conversation_state(self, session_id: str, 
                                      updates: Dict[str, Any]) -> ConversationState:
        """
        Update conversation state with new information.
        
        Args:
            session_id: Session identifier
            updates: Dictionary of updates to apply
            
        Returns:
            Updated ConversationState
        """
        state = await self.get_conversation_state(session_id)
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(state, key):
                setattr(state, key, value)
        
        # Update timestamp
        state.last_updated = datetime.now(timezone.utc)
        
        # Update cache
        self.state_cache[session_id] = state
        
        # Save to Redis
        await self._save_state_to_redis(state)
        
        # Background save to database
        if self.database:
            import asyncio
            asyncio.create_task(self._save_state_to_database(state))
        
        logger.debug(f"Updated conversation state for session {session_id}")
        return state
    
    async def _save_state_to_redis(self, state: ConversationState):
        """Save conversation state to Redis."""
        if not self.redis_context or not self.redis_context._redis_connected:
            return
        
        try:
            state_key = f"conversation_state:{state.session_id}"
            
            # Serialize section progress
            section_progress_data = {}
            for section_num, progress in state.section_progress.items():
                section_progress_data[section_num] = progress.dict()
            
            # Prepare data for Redis
            state_data = {
                "session_id": state.session_id,
                "current_section": state.current_section,
                "total_sections": state.total_sections,
                "section_progress": json.dumps(section_progress_data),
                "conversation_summary": state.conversation_summary,
                "recent_context": json.dumps(state.recent_context),
                "token_count": state.token_count,
                "conversation_stage": state.conversation_stage,
                "last_updated": state.last_updated.isoformat()
            }
            
            # Save to Redis with TTL
            await self.redis_context.redis.hmset(state_key, state_data)
            await self.redis_context.redis.expire(state_key, 86400 * 7)  # 7 days TTL
            
        except Exception as e:
            logger.error(f"Failed to save state to Redis: {e}")
    
    async def _save_state_to_database(self, state: ConversationState):
        """Background task to save state to database."""
        try:
            if self.database:
                # This would be implemented based on your database schema
                pass
        except Exception as e:
            logger.error(f"Failed to save state to database: {e}")
    
    async def update_criteria_completion(self, session_id: str, 
                                       section_number: int,
                                       completed_criteria: List[str],
                                       confidence_scores: Optional[Dict[str, float]] = None) -> ConversationState:
        """
        Update criteria completion for a section.
        
        Args:
            session_id: Session identifier
            section_number: Section number to update
            completed_criteria: List of completed criteria keys
            confidence_scores: Optional confidence scores for criteria
            
        Returns:
            Updated ConversationState
        """
        state = await self.get_conversation_state(session_id)
        
        if section_number not in state.section_progress:
            logger.warning(f"Section {section_number} not found in progress")
            return state
        
        section_progress = state.section_progress[section_number]
        
        # Update completed criteria
        for criteria_key in completed_criteria:
            if criteria_key in section_progress.criteria_missing:
                section_progress.criteria_missing.remove(criteria_key)
            
            if criteria_key not in section_progress.criteria_completed:
                section_progress.criteria_completed.append(criteria_key)
        
        # Calculate completion percentage
        total_criteria = len(section_progress.criteria_completed) + len(section_progress.criteria_missing)
        if total_criteria > 0:
            section_progress.completion_percentage = len(section_progress.criteria_completed) / total_criteria * 100
        
        # Check if section is complete
        section_progress.is_complete = len(section_progress.criteria_missing) == 0
        section_progress.updated_at = datetime.now(timezone.utc)
        
        # Update overall state
        state.section_progress[section_number] = section_progress
        
        # Save state
        await self._save_state_to_redis(state)
        self.state_cache[session_id] = state
        
        logger.info(f"Updated criteria completion for session {session_id}, section {section_number}: "
                   f"{len(section_progress.criteria_completed)}/{total_criteria} complete")
        
        return state
    
    async def advance_to_next_section(self, session_id: str) -> ConversationState:
        """
        Advance to the next section.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Updated ConversationState
        """
        state = await self.get_conversation_state(session_id)
        
        if state.current_section < state.total_sections:
            state.current_section += 1
            logger.info(f"Advanced session {session_id} to section {state.current_section}")
        else:
            logger.info(f"Session {session_id} already at final section")
        
        return await self.update_conversation_state(session_id, {
            "current_section": state.current_section
        })
    
    async def is_section_complete(self, session_id: str, section_number: int) -> bool:
        """
        Check if a section is complete.
        
        Args:
            session_id: Session identifier
            section_number: Section number to check
            
        Returns:
            True if section is complete
        """
        state = await self.get_conversation_state(session_id)
        
        if section_number not in state.section_progress:
            return False
        
        section_progress = state.section_progress[section_number]
        
        # Check completion threshold
        if self.framework_sections:
            section_key = list(self.framework_sections.keys())[section_number - 1]
            section_data = self.framework_sections[section_key]
            completion_threshold = section_data.get("completion_threshold", 0.8)
            
            return section_progress.completion_percentage >= (completion_threshold * 100)
        
        return section_progress.is_complete
    
    async def get_missing_criteria(self, session_id: str, section_number: int) -> List[str]:
        """
        Get missing criteria for a section.
        
        Args:
            session_id: Session identifier
            section_number: Section number
            
        Returns:
            List of missing criteria keys
        """
        state = await self.get_conversation_state(session_id)
        
        if section_number not in state.section_progress:
            return []
        
        return state.section_progress[section_number].criteria_missing
    
    async def get_overall_completion(self, session_id: str) -> float:
        """
        Get overall completion percentage across all sections.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Overall completion percentage (0-100)
        """
        state = await self.get_conversation_state(session_id)
        
        if not state.section_progress:
            return 0.0
        
        total_completion = sum(
            progress.completion_percentage 
            for progress in state.section_progress.values()
        )
        
        return total_completion / len(state.section_progress)
    
    async def get_framework_progress_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get comprehensive framework progress summary.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Framework progress summary
        """
        state = await self.get_conversation_state(session_id)
        
        overall_completion = await self.get_overall_completion(session_id)
        
        sections_summary = {}
        for section_num, progress in state.section_progress.items():
            sections_summary[section_num] = {
                "name": progress.section_name,
                "completion_percentage": progress.completion_percentage,
                "is_complete": progress.is_complete,
                "completed_criteria": len(progress.criteria_completed),
                "missing_criteria": len(progress.criteria_missing),
                "total_criteria": len(progress.criteria_completed) + len(progress.criteria_missing)
            }
        
        return {
            "session_id": session_id,
            "overall_completion": overall_completion,
            "current_section": state.current_section,
            "total_sections": state.total_sections,
            "sections": sections_summary,
            "conversation_turns": len(state.recent_context),
            "last_updated": state.last_updated.isoformat()
        }
    
    async def set_conversation_stage(self, session_id: str, stage: ConversationStage) -> ConversationState:
        """
        Set the conversation stage.
        
        Args:
            session_id: Session identifier
            stage: Conversation stage
            
        Returns:
            Updated ConversationState
        """
        return await self.update_conversation_state(session_id, {
            "conversation_stage": stage.value
        })
    
    async def add_context_note(self, session_id: str, note: str) -> ConversationState:
        """
        Add a context note to recent context.
        
        Args:
            session_id: Session identifier
            note: Context note to add
            
        Returns:
            Updated ConversationState
        """
        state = await self.get_conversation_state(session_id)
        
        # Add note to recent context
        state.recent_context.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "note": note
        })
        
        # Keep only recent context (last 20 items)
        if len(state.recent_context) > 20:
            state.recent_context = state.recent_context[-20:]
        
        return await self.update_conversation_state(session_id, {
            "recent_context": state.recent_context
        })
    
    async def clear_session_state(self, session_id: str):
        """
        Clear conversation state for a session.
        
        Args:
            session_id: Session identifier
        """
        # Remove from cache
        if session_id in self.state_cache:
            del self.state_cache[session_id]
        
        # Clear from Redis
        if self.redis_context and self.redis_context._redis_connected:
            try:
                state_key = f"conversation_state:{session_id}"
                await self.redis_context.redis.delete(state_key)
            except Exception as e:
                logger.error(f"Failed to clear Redis state: {e}")
        
        logger.info(f"Cleared conversation state for session {session_id}")
