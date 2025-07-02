# Tools

Specialized tools used by agents for LLM interactions, assessment, and data processing.

## Files:

- **`llm_tool.py`** - Multi-provider LLM interface (OpenAI, Claude, DeepSeek)
- **`assessment_tool.py`** - Answer quality evaluation using rubrics
- **`scraper_tool.py`** - Website scraping capabilities (to be implemented)

## Current Status:

✅ **LLM Tool** - Multi-provider support with:
- OpenAI GPT integration
- Anthropic Claude integration  
- DeepSeek integration
- Agent-specific LLM routing
- Cost and usage tracking

✅ **Assessment Tool** - Intelligent answer evaluation with:
- Rubric-based scoring (1-10 scale)
- Context-aware follow-up generation
- Both LLM and rule-based assessment modes
- Integration with your detailed rubrics

🚧 **Scraper Tool** - Planned for website content extraction

## Key Features:

- **Multi-LLM Support** - Switch between providers per agent
- **Intelligent Assessment** - Uses your custom rubrics for evaluation
- **Fallback Logic** - Rule-based assessment when LLM unavailable
- **Context Awareness** - Generates relevant follow-up questions
