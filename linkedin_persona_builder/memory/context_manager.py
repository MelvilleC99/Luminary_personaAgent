"""
LinkedIn Persona Builder - Context Manager

Manages conversation context using simple logic - NO LLM calls.
Builds context from conversation history for question generation.
"""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Internal imports
from data.redis.redis_utils import redis_manager
from orchestrator.config import settings

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ConversationContext:
    """Simple conversation context structure"""
    industry: str = "unknown"
    communication_style: str = "unknown"
    user_preferences: Dict[str, Any] = None
    previous_responses: List[str] = None
    response_patterns: Dict[str, Any] = None
    session_metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.user_preferences is None:
            self.user_preferences = {}
        if self.previous_responses is None:
            self.previous_responses = []
        if self.response_patterns is None:
            self.response_patterns = {}
        if self.session_metadata is None:
            self.session_metadata = {}


class ContextManager:
    """
    Manages conversation context using SIMPLE LOGIC - no LLM calls.
    
    Uses keyword matching and pattern analysis to build context for question generation.
    YAML framework provides the intelligence, not this component.
    """
    
    def __init__(self):
        """Initialize context manager"""
        self.redis_manager = redis_manager
        self.max_context_tokens = getattr(settings, 'max_context_tokens', 2000)
        self.max_history_turns = getattr(settings, 'max_history_turns', 12)
        
        logger.info("ContextManager initialized with simple logic approach")
    
    async def build_question_context(self, session_id: str) -> ConversationContext:
        """
        Build context for question generation using simple analysis
        
        Process:
        1. Get conversation history from Redis
        2. Analyze patterns with simple logic
        3. Extract recent responses
        4. Return structured context
        """
        try:
            logger.info(f"Building question context for session: {session_id}")
            
            # Get conversation history
            history = await self.redis_manager.get_conversation_history(
                session_id, 
                count=self.max_history_turns
            )
            
            if not history:
                logger.info("No conversation history found, returning empty context")
                return ConversationContext()
            
            # Analyze using simple logic
            industry = self._detect_industry_simple(history)
            communication_style = self._detect_communication_style_simple(history)
            user_preferences = self._detect_user_preferences_simple(history)
            previous_responses = self._extract_recent_responses(history)
            response_patterns = self._analyze_response_patterns_simple(history)
            
            # Build session metadata
            session_metadata = {
                "total_turns": len(history),
                "session_duration": self._calculate_session_duration(history),
                "last_activity": history[0].get("timestamp") if history else None,
                "user_name": "there"  # Would come from session data
            }
            
            context = ConversationContext(
                industry=industry,
                communication_style=communication_style,
                user_preferences=user_preferences,
                previous_responses=previous_responses,
                response_patterns=response_patterns,
                session_metadata=session_metadata
            )
            
            logger.info(f"Context built - industry: {industry}, style: {communication_style}")
            return context
            
        except Exception as e:
            logger.error(f"Context building failed for session {session_id}: {e}")
            return ConversationContext()
    
    def _detect_industry_simple(self, history: List[Dict[str, Any]]) -> str:
        """Detect industry using simple keyword matching"""
        try:
            # Extract user responses
            user_responses = [
                turn.get("user_input", "").lower() for turn in history 
                if turn.get("user_input")
            ]
            
            if not user_responses:
                return "unknown"
            
            combined_text = " ".join(user_responses)
            
            # Simple keyword matching
            industry_keywords = {
                "saas": ["saas", "software as a service", "subscription", "platform", "api", "cloud"],
                "technology": ["software", "tech", "development", "programming", "coding", "digital"],
                "consulting": ["consulting", "consultant", "advisory", "strategy", "transformation"],
                "ecommerce": ["ecommerce", "e-commerce", "retail", "online store", "shopify", "amazon"],
                "finance": ["finance", "financial", "banking", "investment", "accounting", "fintech"],
                "healthcare": ["healthcare", "medical", "health", "hospital", "clinical", "pharmaceutical"],
                "marketing": ["marketing", "advertising", "campaigns", "social media", "content"],
                "real_estate": ["real estate", "property", "housing", "commercial", "residential"]
            }
            
            # Count matches for each industry
            industry_scores = {}
            for industry, keywords in industry_keywords.items():
                score = sum(1 for keyword in keywords if keyword in combined_text)
                if score > 0:
                    industry_scores[industry] = score
            
            # Return industry with highest score
            if industry_scores:
                detected_industry = max(industry_scores, key=industry_scores.get)
                logger.info(f"Detected industry: {detected_industry} (score: {industry_scores[detected_industry]})")
                return detected_industry
            
            return "unknown"
            
        except Exception as e:
            logger.error(f"Simple industry detection failed: {e}")
            return "unknown"
    
    def _detect_communication_style_simple(self, history: List[Dict[str, Any]]) -> str:
        """Detect communication style using simple pattern analysis"""
        try:
            user_responses = [
                turn.get("user_input", "") for turn in history 
                if turn.get("user_input")
            ]
            
            if len(user_responses) < 2:
                return "unknown"
            
            # Simple pattern analysis
            total_words = sum(len(response.split()) for response in user_responses)
            avg_length = total_words / len(user_responses)
            
            # Check for data/metrics usage
            uses_numbers = any(
                any(char.isdigit() for char in response) or 
                any(word in response.lower() for word in ["percent", "%", "increase", "decrease", "roi"])
                for response in user_responses
            )
            
            # Check for storytelling
            uses_stories = any(
                any(word in response.lower() for word in ["when", "example", "story", "experience", "case"])
                for response in user_responses
            )
            
            # Simple classification
            if avg_length > 20 and uses_numbers:
                return "analytical"
            elif avg_length > 15 and uses_stories:
                return "storytelling"
            elif avg_length < 8:
                return "direct"
            else:
                return "conversational"
                
        except Exception as e:
            logger.error(f"Simple communication style detection failed: {e}")
            return "unknown"
    
    def _detect_user_preferences_simple(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect user preferences using simple analysis"""
        try:
            preferences = {
                "prefers_examples": False,
                "response_length": "medium",
                "needs_clarification": False,
                "industry_specific": False
            }
            
            if not history:
                return preferences
            
            # Count clarification requests
            clarification_count = sum(
                1 for turn in history 
                if turn.get("user_input") and any(
                    phrase in turn["user_input"].lower() 
                    for phrase in ["explain", "what do you mean", "can you", "example", "help"]
                )
            )
            
            # Count follow-ups
            follow_up_count = sum(
                1 for turn in history 
                if turn.get("node_type") == "follow_up"
            )
            
            # Analyze response lengths
            user_responses = [
                turn.get("user_input", "") for turn in history 
                if turn.get("user_input")
            ]
            
            if user_responses:
                avg_response_length = sum(len(r.split()) for r in user_responses) / len(user_responses)
                
                preferences.update({
                    "prefers_examples": clarification_count > len(history) * 0.3,
                    "response_length": "long" if avg_response_length > 20 else "short" if avg_response_length < 8 else "medium",
                    "needs_clarification": follow_up_count > len(history) * 0.4,
                    "industry_specific": avg_response_length > 15  # Longer responses often more industry-specific
                })
            
            return preferences
            
        except Exception as e:
            logger.error(f"User preference detection failed: {e}")
            return {"prefers_examples": False, "response_length": "medium"}
    
    def _extract_recent_responses(self, history: List[Dict[str, Any]], count: int = 3) -> List[str]:
        """Extract recent user responses for context"""
        user_responses = []
        
        # History is in reverse order (most recent first)
        for turn in history:
            if turn.get("user_input") and len(user_responses) < count:
                user_responses.append(turn["user_input"])
        
        return user_responses  # Keep in reverse order (most recent first)
    
    def _analyze_response_patterns_simple(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Simple pattern analysis of user responses"""
        try:
            patterns = {
                "quality_trend": "stable",
                "engagement_level": "medium",
                "consistency": "good"
            }
            
            if len(history) < 3:
                return patterns
            
            # Analyze quality scores if available
            quality_scores = [
                turn.get("quality_score", 5) for turn in history 
                if turn.get("quality_score")
            ]
            
            if len(quality_scores) >= 3:
                recent_avg = sum(quality_scores[:3]) / 3  # First 3 are most recent
                earlier_avg = sum(quality_scores[3:]) / len(quality_scores[3:]) if len(quality_scores) > 3 else recent_avg
                
                if recent_avg > earlier_avg + 1:
                    patterns["quality_trend"] = "improving"
                elif recent_avg < earlier_avg - 1:
                    patterns["quality_trend"] = "declining"
            
            # Analyze engagement based on response length
            user_responses = [
                turn.get("user_input", "") for turn in history 
                if turn.get("user_input")
            ]
            
            if user_responses:
                avg_length = sum(len(r.split()) for r in user_responses) / len(user_responses)
                
                if avg_length > 15:
                    patterns["engagement_level"] = "high"
                elif avg_length < 5:
                    patterns["engagement_level"] = "low"
            
            return patterns
            
        except Exception as e:
            logger.error(f"Pattern analysis failed: {e}")
            return {"quality_trend": "stable", "engagement_level": "medium"}
    
    def _calculate_session_duration(self, history: List[Dict[str, Any]]) -> int:
        """Calculate session duration in minutes"""
        try:
            if not history or len(history) < 2:
                return 0
            
            # Get timestamps from first and last turns
            last_turn = history[0]  # Most recent
            first_turn = history[-1]  # Oldest
            
            first_time = first_turn.get("timestamp")
            last_time = last_turn.get("timestamp")
            
            if first_time and last_time:
                # Parse timestamps and calculate difference
                first_dt = datetime.fromisoformat(first_time.replace('Z', '+00:00'))
                last_dt = datetime.fromisoformat(last_time.replace('Z', '+00:00'))
                
                duration = (last_dt - first_dt).total_seconds() / 60
                return int(duration)
            
            return 0
            
        except Exception as e:
            logger.error(f"Session duration calculation failed: {e}")
            return 0


# Global context manager instance
context_manager = ContextManager()
