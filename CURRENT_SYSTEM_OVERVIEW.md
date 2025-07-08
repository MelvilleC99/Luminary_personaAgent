# 🗂️ CURRENT SYSTEM - KEY FILES & RESPONSIBILITIES

## 🚀 **ENTRY POINTS**
- **`api/endpoints.py`** - FastAPI server, handles HTTP requests from frontend
- **`start_api.sh`** - Script to start the backend server

## 🧠 **CORE AGENTS** 
- **`agents/langgraph_persona_agent.py`** - Main LangGraph conversational agent (ACTIVE)
- **`agents/persona_agent.py`** - Old fragmented agent (FALLBACK ONLY)
- **`agents/base/agent_interface.py`** - Base agent interface

## 🎯 **ORCHESTRATION**
- **`orchestrator/coordinator.py`** - Routes requests to agents, manages sessions
- **`orchestrator/config.py`** - Configuration settings

## 🛠️ **TOOLS** (Used by old agent only)
- **`tools/llm_tool.py`** - LLM provider interface (OpenAI, Anthropic)
- **`tools/framework_assessment_tool.py`** - Old assessment logic (NOT used by LangGraph)
- **`tools/information_extraction_tool.py`** - Old extraction logic (NOT used by LangGraph)
- **`tools/conversation_helpers.py`** - Basic patterns (NOT used by LangGraph)

## 💾 **DATA & MEMORY**
- **`knowledge/framework_criteria.yaml`** - 60+ criteria definitions across 6 sections
- **`memory/session_manager.py`** - Session tracking and progress
- **`memory/context_manager.py`** - Message storage and retrieval
- **`database/supabase_client.py`** - Database connections

## 📝 **PROMPTS & KNOWLEDGE**
- **`prompts/persona_agent_prompt.txt`** - System prompt for old agent
- **`knowledge/framework_criteria.yaml`** - Framework definitions

## 🧪 **TESTING**
- **`test_langgraph_agent.py`** - Tests for new LangGraph agent

---

## ❌ **UNUSED FILES** (Moved to UNUSED_FILES/)
- `agents/question_agent.py.UNUSED` - Old Q&A agent
- `tools/assessment_tool.py.UNUSED` - Old assessment tool
- `orchestrator/main.py.UNUSED` - Unused entry point
- Various test files moved to UNUSED_FILES/

---

## 🔄 **CURRENT REQUEST FLOW**

```
Frontend → api/endpoints.py → orchestrator/coordinator.py → agents/langgraph_persona_agent.py
```

The LangGraph agent handles everything internally (no tool chain) and returns responses to the coordinator.
