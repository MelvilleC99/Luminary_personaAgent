"""
Simple conversation flow helpers for more natural interactions.
"""

def get_natural_follow_up(extracted_info, missing_criteria):
    """Get a natural follow-up based on what was extracted."""
    
    # Check what we extracted
    extracted_text = " ".join([e.get('extracted_value', '') for e in extracted_info])
    
    # Natural progression based on AI/automation expertise
    if any(word in extracted_text.lower() for word in ['ai', 'automation', 'agent']):
        if not any(c.get('criteria_key') == 'target_audience' for c in missing_criteria):
            return "That's fascinating! AI and automation are definitely transforming businesses. I'm curious - who specifically do you help with this? What type of companies or roles benefit most from your expertise?"
        
        elif not any(c.get('criteria_key') == 'core_problem' for c in missing_criteria):
            return "I can tell you're passionate about this space. What specific challenges do your ideal clients face that you're uniquely positioned to solve?"
            
        elif not any(c.get('criteria_key') == 'niche_expertise' for c in missing_criteria):
            return "What makes your approach to AI and automation different? What's your specific methodology or framework?"
    
    # Generic natural follow-ups
    follow_ups = [
        "That's great insight! Tell me more about who specifically benefits from your expertise.",
        "I can see why that would be valuable. What challenges do your ideal clients face?",
        "What makes your approach unique in this space?",
        "Who are the people that get the most value from what you do?"
    ]
    
    return follow_ups[0]

def get_opening_question():
    """Get a simple opening question."""
    return "What's something about your business that you could talk about for hours?"
