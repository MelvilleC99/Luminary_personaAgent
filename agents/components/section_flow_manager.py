"""
Section Flow Manager for Persona Agent.
Manages the logical flow through the 6 persona sections.
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SectionFlowManager:
    """
    Manages the logical flow through persona building sections.
    Knows which section to work on and what questions to ask.
    """
    
    def __init__(self, framework_criteria: Dict[str, Any]):
        self.framework_criteria = framework_criteria
        self.sections = list(framework_criteria.keys())
        self.total_sections = len(self.sections)
        
        # Section flow questions
        self.section_questions = {
            1: [
                "What's a broad topic or domain you understand deeply - one you could speak on confidently for hours?",
                "What's your specific niche or specialization within that domain?",
                "Who is your ideal client? Include industry, role/title, and business size.",
                "What's the #1 pain point or problem you solve for them?",
                "What specific results or transformation do your clients get?"
            ],
            2: [
                "How would you describe your brand personality in 3-4 words?",
                "What are your core values that guide your work?",
                "What's your origin story - how did you get into this field?",
                "What formative experience shaped your approach?",
                "What reputation do you want to be known for?"
            ],
            3: [
                "What's your elevator pitch in 30 seconds?",
                "What makes your approach unique or different?",
                "What methods or frameworks do you use?",
                "What's a contrarian belief you hold in your field?",
                "What services or solutions do you offer?"
            ],
            4: [
                "How would you describe your communication style?",
                "What tone do you use when speaking to clients?",
                "Are there any signature phrases or concepts you use?",
                "What's your content approach - educational, inspirational, analytical?",
                "Who are some communicators you admire or model?"
            ],
            5: [
                "What's your main goal with your content?",
                "What struggles does your audience face daily?",
                "What are their biggest desires or aspirations?",
                "Can you share a client success story?",
                "What emotional impact do you want to create?"
            ],
            6: [
                "What's your long-term vision for your business?",
                "What legacy do you want to leave in your field?",
                "How do you measure success beyond money?",
                "What would make you feel like you've 'made it'?",
                "What impact do you want to have on your industry?"
            ]
        }
    
    def get_section_name(self, section_number: int) -> str:
        """Get the name of a section."""
        if section_number <= 0 or section_number > self.total_sections:
            return "Unknown Section"
        
        section_key = self.sections[section_number - 1]
        return self.framework_criteria[section_key].get("section_name", section_key)
    
    def get_section_intro(self, section_number: int) -> str:
        """Get introduction text for a section."""
        section_name = self.get_section_name(section_number)
        
        intros = {
            1: f"Great! Let's start with {section_name}. This helps me understand your expertise and who you serve.",
            2: f"Perfect! Now let's explore {section_name}. This is about your unique identity and what drives you.",
            3: f"Excellent! Moving to {section_name}. Here we'll define what makes you stand out.",
            4: f"Fantastic! Let's work on {section_name}. This is about how you communicate and connect.",
            5: f"Great progress! Now {section_name}. This focuses on your content strategy and audience.",
            6: f"Almost there! Finally, {section_name}. This is about your bigger picture and impact."
        }
        
        return intros.get(section_number, f"Let's work on {section_name}.")
    
    def get_next_question(self, section_number: int, questions_asked: List[str]) -> Optional[str]:
        """Get the next question for a section."""
        if section_number not in self.section_questions:
            return None
        
        available_questions = self.section_questions[section_number]
        
        # Find first question not yet asked
        for question in available_questions:
            if question not in questions_asked:
                return question
        
        return None
    
    def should_advance_section(self, section_number: int, responses_count: int, quality_score: float = 0.7) -> bool:
        """Determine if we should advance to the next section."""
        # Basic rules for section advancement
        if section_number > self.total_sections:
            return False
        
        # Need at least 2 responses per section with decent quality
        min_responses = 2
        min_quality = 0.6
        
        return responses_count >= min_responses and quality_score >= min_quality
    
    def get_section_completion_message(self, section_number: int) -> str:
        """Get completion message for a section."""
        section_name = self.get_section_name(section_number)
        
        if section_number < self.total_sections:
            next_section = self.get_section_name(section_number + 1)
            return f"Great work on {section_name}! Let's move to the next section: {next_section}."
        else:
            return f"Excellent! You've completed all sections. I have everything I need to create your comprehensive persona."
    
    def get_follow_up_question(self, section_number: int, user_response: str) -> Optional[str]:
        """Generate a follow-up question based on user response."""
        # Simple follow-up logic based on response length and content
        if len(user_response.strip()) < 30:
            return "Could you tell me more about that? I'd love to understand the details."
        
        # Section-specific follow-ups
        follow_ups = {
            1: [
                "What specific outcomes do your clients achieve?",
                "How do you typically work with clients on this?",
                "What makes your approach different from others?"
            ],
            2: [
                "What experiences shaped this approach?",
                "How does this show up in your work?",
                "What would clients say about this aspect of you?"
            ],
            3: [
                "Can you give me an example of this in action?",
                "How do you communicate this to potential clients?",
                "What results have you seen from this approach?"
            ],
            4: [
                "How does this style connect with your audience?",
                "What feedback do you get about your communication?",
                "Are there specific words or phrases you use often?"
            ],
            5: [
                "What transformation do you want to create?",
                "How do you measure this impact?",
                "What would success look like for your audience?"
            ],
            6: [
                "What steps are you taking toward this vision?",
                "How will you know when you've achieved this?",
                "What impact do you want to have on others?"
            ]
        }
        
        section_follow_ups = follow_ups.get(section_number, [])
        if section_follow_ups:
            # Simple selection - could be made more intelligent
            return section_follow_ups[0]
        
        return None
    
    def analyze_response_quality(self, response: str) -> float:
        """Analyze the quality of a user response."""
        # Simple quality scoring
        score = 0.0
        
        # Length check
        if len(response) > 100:
            score += 0.3
        elif len(response) > 50:
            score += 0.2
        elif len(response) > 20:
            score += 0.1
        
        # Specificity indicators
        specific_words = ["specifically", "example", "for instance", "such as", "like", "including"]
        for word in specific_words:
            if word in response.lower():
                score += 0.1
                break
        
        # Business terms
        business_terms = ["client", "customer", "business", "company", "service", "solution", "problem", "result"]
        business_count = sum(1 for term in business_terms if term in response.lower())
        score += min(business_count * 0.1, 0.3)
        
        # Personal indicators
        personal_terms = ["I", "my", "me", "our", "we"]
        if any(term in response for term in personal_terms):
            score += 0.1
        
        return min(score, 1.0)
    
    def get_section_progress(self, section_number: int, questions_asked: int, responses_received: int) -> Dict[str, Any]:
        """Get progress information for a section."""
        total_questions = len(self.section_questions.get(section_number, []))
        
        return {
            "section_number": section_number,
            "section_name": self.get_section_name(section_number),
            "questions_asked": questions_asked,
            "responses_received": responses_received,
            "total_questions": total_questions,
            "completion_percentage": min((responses_received / max(total_questions, 1)) * 100, 100),
            "is_complete": responses_received >= max(total_questions - 1, 2)  # Allow completion with most questions answered
        }
