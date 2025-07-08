"""
Usage tracking and cost monitoring for persona agent.
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

class UsageTracker:
    """Track API usage, costs, and performance metrics."""
    
    def __init__(self):
        self.usage_data = {
            "sessions": {},
            "api_calls": [],
            "costs": {"total": 0.0, "by_provider": {}},
            "performance": [],
            "errors": []
        }
        self.usage_file = Path(__file__).parent.parent / "logs" / "usage_tracking.json"
        self._load_existing_data()
    
    def _load_existing_data(self):
        """Load existing usage data."""
        try:
            if self.usage_file.exists():
                with open(self.usage_file, 'r') as f:
                    self.usage_data.update(json.load(f))
        except Exception:
            pass  # Start fresh if corrupted
    
    def _save_data(self):
        """Save usage data to file."""
        try:
            self.usage_file.parent.mkdir(exist_ok=True)
            with open(self.usage_file, 'w') as f:
                json.dump(self.usage_data, f, indent=2, default=str)
        except Exception as e:
            print(f"Failed to save usage data: {e}")
    
    def track_session_start(self, session_id: str, user_id: Optional[str] = None):
        """Track session start."""
        self.usage_data["sessions"][session_id] = {
            "user_id": user_id,
            "start_time": datetime.utcnow().isoformat(),
            "questions_completed": 0,
            "api_calls": 0,
            "total_cost": 0.0,
            "status": "active"
        }
        self._save_data()
    
    def track_api_call(self, session_id: str, provider: str, model: str, 
                      tokens: int, cost: float, duration: float):
        """Track API call with cost and performance."""
        
        api_call = {
            "session_id": session_id,
            "provider": provider,
            "model": model,
            "tokens": tokens,
            "cost": cost,
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.usage_data["api_calls"].append(api_call)
        
        # Update totals
        self.usage_data["costs"]["total"] += cost
        if provider not in self.usage_data["costs"]["by_provider"]:
            self.usage_data["costs"]["by_provider"][provider] = 0.0
        self.usage_data["costs"]["by_provider"][provider] += cost
        
        # Update session data
        if session_id in self.usage_data["sessions"]:
            self.usage_data["sessions"][session_id]["api_calls"] += 1
            self.usage_data["sessions"][session_id]["total_cost"] += cost
        
        self._save_data()
    
    def track_question_completion(self, session_id: str, question_id: int, 
                                score: float, follow_ups: int = 0):
        """Track question completion."""
        if session_id in self.usage_data["sessions"]:
            self.usage_data["sessions"][session_id]["questions_completed"] += 1
        
        performance_data = {
            "session_id": session_id,
            "question_id": question_id,
            "score": score,
            "follow_ups": follow_ups,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.usage_data["performance"].append(performance_data)
        self._save_data()
    
    def track_error(self, session_id: str, error_type: str, error_message: str, 
                   component: str):
        """Track errors for debugging."""
        error_data = {
            "session_id": session_id,
            "error_type": error_type,
            "error_message": error_message,
            "component": component,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.usage_data["errors"].append(error_data)
        self._save_data()
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get stats for a specific session."""
        session_data = self.usage_data["sessions"].get(session_id, {})
        api_calls = [call for call in self.usage_data["api_calls"] 
                    if call["session_id"] == session_id]
        
        return {
            "session_info": session_data,
            "api_calls_count": len(api_calls),
            "total_tokens": sum(call["tokens"] for call in api_calls),
            "total_cost": session_data.get("total_cost", 0.0),
            "avg_response_time": sum(call["duration"] for call in api_calls) / len(api_calls) if api_calls else 0
        }
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall system stats."""
        total_sessions = len(self.usage_data["sessions"])
        total_api_calls = len(self.usage_data["api_calls"])
        total_errors = len(self.usage_data["errors"])
        
        return {
            "total_sessions": total_sessions,
            "total_api_calls": total_api_calls,
            "total_cost": self.usage_data["costs"]["total"],
            "cost_by_provider": self.usage_data["costs"]["by_provider"],
            "total_errors": total_errors,
            "avg_questions_per_session": sum(s.get("questions_completed", 0) 
                                           for s in self.usage_data["sessions"].values()) / max(total_sessions, 1)
        }
    
    def display_session_stats(self, session_id: str):
        """Display session stats in terminal."""
        stats = self.get_session_stats(session_id)
        if stats["session_info"]:
            print(f"Session Stats [{session_id[:8]}...]:")
            print(f"  API Calls: {stats['api_calls_count']}")
            print(f"  Total Tokens: {stats['total_tokens']:,}")
            print(f"  Total Cost: ${stats['total_cost']:.4f}")
            print(f"  Avg Response Time: {stats['avg_response_time']:.0f}ms")
    
    def display_overall_stats(self):
        """Display overall system stats in terminal."""
        stats = self.get_overall_stats()
        print("System Usage Summary:")
        print(f"  Total Sessions: {stats['total_sessions']}")
        print(f"  Total API Calls: {stats['total_api_calls']}")
        print(f"  Total Cost: ${stats['total_cost']:.4f}")
        print(f"  Avg Questions/Session: {stats['avg_questions_per_session']:.1f}")
        if stats['cost_by_provider']:
            print("  Cost by Provider:")
            for provider, cost in stats['cost_by_provider'].items():
                print(f"    {provider}: ${cost:.4f}")
        if stats['total_errors'] > 0:
            print(f"  Total Errors: {stats['total_errors']}")


# Global usage tracker
usage_tracker = UsageTracker()
