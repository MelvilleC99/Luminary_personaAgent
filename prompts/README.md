# Prompts - Streamlined Architecture

System prompts and assessment templates for the persona building system.

## Architecture Overview

The system uses a **single-layer prompt architecture** for efficiency:

1. **Main System Prompt**: `question_agent_prompt.txt` - Sets context and behavior
2. **Per-Question Assessment Prompts**: `assessment/question_X_assessment.txt` - Specific scoring criteria

## Files Structure

```
prompts/
├── question_agent_prompt.txt           # Main system prompt for question agent
└── assessment/                         # Per-question assessment prompts
    ├── question_1_assessment.txt       # Q1: Broad expertise assessment
    ├── question_2_assessment.txt       # Q2: Niche specialization assessment
    └── question_3_assessment.txt       # Q3: Target audience assessment
```

## Design Principles

### ✅ Streamlined Approach
- **Single system prompt** - No redundant assessment agent prompts
- **Minimal assessment prompts** - 200-400 characters each
- **No context injection** - Each question assessed independently
- **No examples in prompts** - LLM doesn't need 10 examples to understand "be specific"

### ✅ Performance Optimized
- **Total prompt size**: ~1,100 chars (vs previous ~2,600 chars)
- **Timeout prevention**: Aggressive 2000 char limit with fallbacks
- **Fast assessment**: 30-second timeout vs previous 60-second

### ✅ Maintainable
- **No JSON rubrics** - Assessment logic lives in prompts, not separate files
- **No redundant files** - Single source of truth per question
- **Clean separation** - System behavior vs assessment criteria

## Assessment Prompt Format

Each question assessment prompt follows this structure:

```
ASSESS Q[N]: "[Question text]"

CRITERIA: [Specific requirements for this question]

SCORE: 1-10 (7+ = advance, <7 = follow-up)
FOLLOW-UP: "[Generic follow-up template]"

Respond JSON: {"score": X, "needs_follow_up": true/false, "follow_up_question": "...", "reasoning": "..."}
```

## Removed Files (Archived)

The following files were removed to eliminate redundancy:
- `system_prompts/assessment_agent_prompt.txt.backup` - Redundant system prompt
- `../knowledge/assessment_rubrics.json.backup` - Duplicate of prompt logic

## Usage

Prompts are loaded by the assessment tool:

```python
prompt_path = Path(__file__).parent.parent / "prompts" / "assessment" / f"question_{question_id}_assessment.txt"
```

## Performance Metrics

**Before Streamlining:**
- Q1: 2,300 chars total
- Q2: 2,600 chars total (with context injection)
- Q3: 3,100 chars total (with Q1+Q2 context)

**After Streamlining:**
- Q1: 700 chars total (69.6% reduction)
- Q2: 700 chars total (73.1% reduction)  
- Q3: 700 chars total (77.4% reduction)

This eliminates the Q2 timeout issue and makes the system robust for 500+ character user responses.