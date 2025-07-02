# Luminary Persona Agent

A sophisticated AI-powered persona building system that creates detailed psychological profiles through intelligent questioning and assessment. The system leverages multiple LLM providers to generate comprehensive persona insights through 30 carefully crafted questions.

## Features

### 🧠 **Intelligent Persona Building**
- 30 carefully crafted questions across 3 categories: Values & Beliefs, Goals & Aspirations, Communication & Decision-Making
- Real-time assessment and scoring system
- Context-aware follow-up questions based on previous responses

### 🤖 **Multi-LLM Support**
- **OpenAI GPT-4o** (primary) - Fast and reliable
- **Anthropic Claude** (fallback) - Deep reasoning capabilities  
- **DeepSeek** (experimental) - Cost-effective alternative
- Automatic failover between providers

### 🎨 **Modern Web Interface**
- Clean, intuitive Streamlit-based UI
- Real-time progress tracking
- Session management with database persistence
- Responsive design for all devices

### 🏗️ **Enterprise Architecture**
- Modular agent-based design with BaseAgent interface
- Comprehensive error handling and logging
- Database integration with Supabase
- RESTful API endpoints for integration
- Rate limit optimization and context management

## Quick Start

### Prerequisites
- Python 3.9+ 
- OpenAI API key
- Supabase account (optional, for session persistence)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/MelvilleC99/Luminary_agent.git
cd Luminary_agent
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
```env
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key  # Optional
SUPABASE_URL=your_supabase_url            # Optional
SUPABASE_KEY=your_supabase_key            # Optional
```

### Running the Application

**Option 1: Streamlit Web Interface (Recommended)**
```bash
streamlit run ui/streamlit_app.py
```

**Option 2: FastAPI Backend**
```bash
./start_api.sh
# Or manually: uvicorn api.endpoints:app --reload
```

## System Architecture

```
luminary_persona_agent/
├── agents/              # Core agent implementations
│   ├── base/           # BaseAgent interface
│   └── question_agent.py
├── tools/              # LLM and assessment tools
│   ├── llm_tool.py     # Multi-provider LLM interface
│   └── assessment_tool.py
├── database/           # Data persistence layer
├── memory/             # Session and context management
├── orchestrator/       # System coordination
├── ui/                 # Streamlit web interface
├── api/                # FastAPI endpoints
├── prompts/            # System prompts and templates
└── knowledge/          # Question database
```

## Key Components

### 🔧 **LLM Tool (`tools/llm_tool.py`)**
- Multi-provider support with intelligent fallback
- Optimized for GPT-4o with 60-second timeout
- Comprehensive error handling and retry logic
- Rate limit management

### 🎯 **Assessment Tool (`tools/assessment_tool.py`)**
- Context-aware assessment with truncation (200 chars)
- Prompt size monitoring and optimization
- Intelligent scoring system
- Follow-up question generation

### 💾 **Database Integration**
- Supabase integration for session persistence
- Clean schema with user sessions and responses
- Automatic session management
- Optional offline mode

### 🧩 **Agent Architecture**
- BaseAgent interface for extensibility
- Question Agent for persona building
- Modular design for easy extension
- Comprehensive logging throughout

## Performance Optimizations

### ✅ **Rate Limit Testing Results**
- **Single requests**: ~1.75s average
- **5 concurrent**: All successful in 1.96s
- **10 concurrent**: All successful in 2.96s  
- **20 concurrent**: All successful in 3.18s
- **Zero rate limit errors** with production API keys

### ⚡ **Context Management**
- Q1→Q2 transitions: **3-4 seconds** (down from 60+ seconds)
- Context truncation prevents API timeouts
- Optimized prompt sizes with monitoring
- Intelligent context bleeding prevention

## Usage Examples

### Basic Persona Building
```python
from agents.question_agent import QuestionAgent
from tools.llm_tool import LLMTool

# Initialize agent
llm_tool = LLMTool()
agent = QuestionAgent(llm_tool=llm_tool)

# Start persona building session
session_id = agent.start_session("user123")
response = agent.process_question(session_id, "What motivates you?", "Making a positive impact")
```

### API Integration
```python
import requests

# Submit response via API
response = requests.post("http://localhost:8000/submit_response", json={
    "session_id": "session123",
    "question_text": "What are your core values?", 
    "user_response": "Integrity and compassion"
})
```

## Development

### Running Tests
```bash
pytest tests/
```

### Code Formatting
```bash
black . --line-length 88
```

### Development Setup
```bash
# Install development dependencies
pip install -r requirements.txt

# Run with auto-reload
streamlit run ui/streamlit_app.py --server.runOnSave true
```

## Configuration

### LLM Provider Priority
1. **OpenAI GPT-4o** (fastest, most reliable)
2. **Anthropic Claude** (fallback for complex reasoning)
3. **DeepSeek** (cost-effective backup)

### Timeouts and Limits
- **OpenAI timeout**: 60 seconds
- **Context truncation**: 200 characters
- **Max prompt size**: 8000 characters (with fallback)
- **Assessment warning**: 4000 characters

## Troubleshooting

### Common Issues

**Q1→Q2 hanging (resolved)**
- ✅ Fixed with context truncation
- ✅ Optimized prompt sizes
- ✅ Added timeout handling

**Rate limits**
- ✅ Tested up to 20 concurrent requests
- ✅ Zero errors with production keys
- ✅ Intelligent retry logic

**Database connectivity**
- Check Supabase credentials in `.env`
- Verify network connectivity
- Falls back to memory-only mode if needed

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Roadmap

- [ ] Additional LLM providers (Gemini, Llama)
- [ ] Voice input/output capabilities
- [ ] Advanced persona analytics and insights
- [ ] Multi-language support
- [ ] Mobile app development
- [ ] Enterprise SSO integration

## Support

For issues and questions:
- 📧 Email: support@luminairy.ai
- 🐛 Issues: [GitHub Issues](https://github.com/MelvilleC99/Luminary_agent/issues)
- 📖 Documentation: [Wiki](https://github.com/MelvilleC99/Luminary_agent/wiki)

---

**Built with ❤️ by the Luminary Team**