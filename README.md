# Luminary Persona Agent

An intelligent persona-building agent that conducts structured Q&A sessions, scrapes company websites, and generates detailed marketing personas for conversion-focused content strategy.

## 🚀 Features

- **Interactive Q&A System**: Guided conversation through 30 structured questions across 6 sections
- **Streamlined Assessment**: Fast, efficient answer evaluation with minimal prompt overhead
- **Website Scraping**: Extracts comprehensive company information using structured templates
- **Persona Synthesis**: Generates detailed marketing personas using collected data and Luminary Hub methodology
- **Session Management**: Persistent sessions with seamless resume capability
- **Multi-LLM Support**: OpenAI, Claude, and DeepSeek integration with smart routing
- **Production Monitoring**: Comprehensive logging, usage tracking, and cost monitoring
- **Database Integration**: Full Supabase integration with session persistence

## 🏗️ Architecture

```
persona-agent/
├── orchestrator/          # Main coordination and entry point
├── agents/               # Specialized agents (Question, Scraper, Persona)
├── memory/              # Session and context management
├── tools/               # LLM, scraping, and assessment tools
├── knowledge/           # Questions and reference materials
├── prompts/             # Streamlined system prompts and assessment templates
├── database/            # Supabase integration and models
├── logging/             # Error tracking and debugging
├── admin/               # Usage tracking and monitoring
├── api/                 # FastAPI endpoints
├── logs/                # Log files (auto-generated)
└── ui/                  # Streamlit testing interface
```

## ⚡ Performance Optimizations

### Streamlined Prompt Architecture
- **77% smaller prompts** - Eliminated redundant system prompts and context injection
- **Fast assessment** - 30-second timeouts with aggressive fallbacks
- **Independent questions** - No context bleeding between questions
- **Robust input handling** - Handles 500+ character responses without timeouts

### Before vs After
- **Q1**: 2,300 → 700 chars (69.6% reduction)
- **Q2**: 2,600 → 700 chars (73.1% reduction)
- **Q3**: 3,100 → 700 chars (77.4% reduction)

## Quick Start

### 1. Environment Setup

```bash
# Clone and navigate to project
cd luminary_persona_agent

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
cp .env.example .env
# Edit .env with your API keys and configuration
```

### 2. Database Setup

```bash
# Supabase database setup will be automated
# Ensure your SUPABASE_URL and SUPABASE_KEY are configured in .env
```

### 3. Run the Application

**Testing Interface (Streamlit):**
```bash
streamlit run ui/streamlit_app.py
```

**API Server (FastAPI):**
```bash
uvicorn api.endpoints:app --reload --host localhost --port 8000
```

## Configuration

### LLM Assignments
Configure which LLM to use for each agent in your `.env` file:

```env
QUESTION_AGENT_LLM=openai      # Conversational flow
ASSESSMENT_AGENT_LLM=openai    # Answer evaluation (streamlined)
SCRAPER_AGENT_LLM=openai       # Structured extraction
PERSONA_AGENT_LLM=claude       # Long-form synthesis
```

### Assessment Settings
```env
ASSESSMENT_THRESHOLD=7.0    # Minimum score to proceed
MAX_FOLLOW_UPS=3           # Maximum follow-up questions per question
```

## Usage

### 1. Start a Session
The agent will guide you through 30 questions across 6 sections:
- Core Expertise & ICP
- Brand Personality & DNA
- Positioning & Expertise
- Voice, Style & Tone
- Content Goals & Audience  
- Long-term Vision & Metrics

### 2. Provide Company Website
Share your company website URL for automated information extraction.

### 3. Answer Questions
The agent will:
- Ask questions sequentially
- Assess answer quality (1-10 scale) using streamlined prompts
- Ask follow-up questions if more detail is needed (no context injection)
- Move to next question when satisfied

### 4. Generate Persona
Once all questions are complete, the agent synthesizes:
- Strategic client persona
- Deep ICP psychology layer
- Differentiators & relevance mapping
- Solution positioning template
- Brand voice & messaging map
- Offer & conversion insights

## Development

### Project Structure
- **Orchestrator**: Main coordination logic
- **Agents**: Specialized AI agents for different tasks
- **Memory**: Session persistence and context management
- **Tools**: Reusable components for LLM calls, web scraping
- **Knowledge**: Question bank and reference materials
- **Prompts**: Streamlined assessment templates

### Adding New Questions
1. Update `knowledge/questions.json`
2. Create streamlined assessment prompt in `prompts/assessment/question_N_assessment.txt`
3. Test with the question agent

### Customizing Prompts
All prompts are stored in `prompts/` directory:
- Main system prompt: `question_agent_prompt.txt`
- Assessment prompts: `assessment/question_X_assessment.txt`

## API Documentation

Once running, visit `http://localhost:8000/docs` for interactive API documentation.

## Troubleshooting

### Common Issues
- **Q2 Timeout Fixed**: Streamlined prompts prevent the previous Q2 timeout issue
- **Large User Responses**: System now handles 500+ character responses robustly
- **Prompt Size Limits**: Aggressive 2000 character limits with fallbacks prevent LLM timeouts

## Support

For issues and questions, check the project documentation or open an issue.