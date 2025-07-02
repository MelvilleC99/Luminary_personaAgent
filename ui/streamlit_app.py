"""
Streamlit testing interface for the Luminary Persona Agent.
"""

import streamlit as st
import asyncio
import sys
import os
import time
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging for debugging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

from orchestrator.coordinator import PersonaCoordinator
from orchestrator.config import settings


@st.cache_resource
def initialize_coordinator():
    """Initialize the coordinator (cached for performance)."""
    try:
        coordinator = PersonaCoordinator()
        return coordinator
    except Exception as e:
        st.error(f"Failed to initialize coordinator: {e}")
        return None


async def start_new_session(coordinator, website_url=None):
    """Start a new persona building session."""
    return await coordinator.start_session(
        user_id="streamlit_user",
        website_url=website_url
    )


async def process_input(coordinator, session_id, user_input):
    """Process user input."""
    return await coordinator.process_user_input(session_id, user_input)


async def get_session_status(coordinator, session_id):
    """Get session status."""
    return await coordinator.get_session_status(session_id)


def main():
    """Main Streamlit app."""
    st.set_page_config(
        page_title="Luminary Persona Agent",
        page_icon="🎯",
        layout="wide"
    )
    
    st.title("🎯 Luminary Persona Agent")
    st.markdown("Build comprehensive marketing personas through intelligent Q&A")
    
    # Initialize coordinator
    coordinator = initialize_coordinator()
    if not coordinator:
        st.stop()
    
    # Sidebar for session management
    with st.sidebar:
        st.header("Session Management")
        
        # Health check
        if st.button("Health Check"):
            with st.spinner("Checking system health..."):
                health = asyncio.run(coordinator.health_check())
                st.json(health)
        
        st.divider()
        
        # Website URL input
        website_url = st.text_input(
            "Company Website (optional)",
            placeholder="https://example.com",
            help="Provide your company website for automated data extraction"
        )
        
        # Start new session
        if st.button("Start New Session", type="primary"):
            with st.spinner("Starting new session..."):
                result = asyncio.run(start_new_session(coordinator, website_url))
                st.session_state.current_session = result.get("session_id")
                st.session_state.session_result = result
                st.rerun()
    
    # Main interface
    if "current_session" not in st.session_state:
        st.info("👋 Welcome! Click 'Start New Session' in the sidebar to begin building your persona.")
        
        # Show system information
        with st.expander("System Information"):
            st.markdown("### Available Components")
            st.markdown("- **Session Manager**: Handles persistent sessions")
            st.markdown("- **Context Manager**: Manages conversation history")
            st.markdown("- **LLM Tool**: Multi-provider AI support")
            st.markdown("- **Coordinator**: Orchestrates all agents")
            
            st.markdown("### Configuration")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Debug Mode**: {settings.debug}")
                st.markdown(f"**Max Follow-ups**: {settings.max_follow_ups}")
            with col2:
                st.markdown(f"**Assessment Threshold**: {settings.assessment_threshold}")
                st.markdown(f"**Session Timeout**: {settings.session_timeout_hours}h")
        
        return
    
    # Display current session info
    session_id = st.session_state.current_session
    
    # Message counter
    message_count = len(st.session_state.get("messages", []))
    if message_count > 20:
        st.warning(f"⚠️ {message_count} messages in this session. Consider starting fresh to avoid limits.")
    else:
        st.info(f"📧 {message_count} messages | Session: `{session_id}`")
    
    # Get session status
    with st.spinner("Loading session status..."):
        status = asyncio.run(get_session_status(coordinator, session_id))
    
    if "error" in status:
        st.error(f"Error: {status['error']}")
        return
    
    # Display progress
    progress = status.get("progress", {})
    if progress:
        st.progress(progress.get("progress_percentage", 0) / 100)
        st.caption(
            f"Question {progress.get('current_question', 1)}/30 "
            f"({progress.get('questions_completed', 0)} completed)"
        )
    
    # Chat interface
    st.header("💬 Conversation")
    
    # Display conversation history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Show initial session result
    if "session_result" in st.session_state:
        result = st.session_state.session_result
        if "message" in result:
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["message"]
            })
        del st.session_state.session_result
    
    # Display messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # User input
    if prompt := st.chat_input("Type your answer here..."):
        # Add user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Process input and get response
        with st.chat_message("assistant"):
            with st.spinner("Processing your answer..."):
                
                # Add debug info
                start_time = time.time()
                st.write("🔍 **Debug Info:**")
                debug_container = st.empty()
                debug_container.write(f"⏱️ Started processing at {datetime.now().strftime('%H:%M:%S')}")
                
                try:
                    response = asyncio.run(process_input(coordinator, session_id, prompt))
                    processing_time = time.time() - start_time
                    
                    debug_container.write(f"✅ Completed in {processing_time:.2f}s")
                    
                    if "error" in response:
                        st.error(f"❌ Error: {response['error']}")
                        debug_container.write(f"❌ Error details: {response}")
                    else:
                        message = response.get("message", "Response received.")
                        st.markdown(message)
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": message
                        })
                        
                        # Show debug info
                        with st.expander("🔍 Debug Details"):
                            st.json(response)
                            
                except Exception as e:
                    processing_time = time.time() - start_time
                    st.error(f"❌ Exception: {e}")
                    debug_container.write(f"💥 Exception after {processing_time:.2f}s: {e}")
                    
                    # Show full traceback
                    import traceback
                    with st.expander("🔍 Full Error Details"):
                        st.code(traceback.format_exc())
    
    # Session details in expander
    with st.expander("Session Details"):
        st.json(status)


if __name__ == "__main__":
    main()
