from typing import Dict, Any, Callable, Optional, Union
from langgraph.graph import StateGraph, Graph
from langgraph.graph.message import MessageGraph
from langgraph.prebuilt import ToolInvocation, ToolExecutor
from data.redis.schemas import SessionState, PersonaData, ConversationTurn, NodeType
import logging
logger = logging.getLogger(__name__)


# Define GraphState for LangGraph
class GraphState(dict):
    """
    LangGraph state object that flows between nodes
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Ensure required fields exist
        self.setdefault("session_id", "")
        self.setdefault("user_id", "")
        self.setdefault("user_input", "")
        self.setdefault("agent_response", "")
        self.setdefault("current_section", 1)
        self.setdefault("current_criterion", "")
        self.setdefault("follow_up_attempts", 0)
        self.setdefault("requires_user_input", True)
        self.setdefault("session_complete", False)
        self.setdefault("next_node", "")
        self.setdefault("error_message", "")


class WorkflowManager:
    """
    Manages LangGraph workflow construction and execution
    """
    
    def __init__(self):
        self.graph: Optional[Graph] = None
        self.nodes: Dict[str, Callable] = {}
    
    def build_graph(self) -> Graph:
        """Construct LangGraph workflow with nodes and edges"""
        try:
            # Create StateGraph
            workflow = StateGraph(GraphState)
            
            # Create and register nodes
            self.nodes = self.create_nodes()
            
            # Add nodes to workflow
            for node_name, node_func in self.nodes.items():
                workflow.add_node(node_name, node_func)
            
            # Define edges and routing
            self._add_edges(workflow)
            
            # Set entry point
            workflow.set_entry_point("greeting")
            
            # Compile graph
            self.graph = workflow.compile()
            
            logger.info("LangGraph workflow built successfully")
            return self.graph
            
        except Exception as e:
            logger.error(f"LangGraph workflow build failed: {e}")
            raise
    
    def create_nodes(self) -> Dict[str, Callable]:
        """Initialize all LangGraph nodes"""
        try:
            # Import node implementations from correct path
            from agent.langgraph_nodes.greeting_node import greeting_node
            from agent.langgraph_nodes.question_node import question_node
            from agent.langgraph_nodes.evaluation_node import evaluation_node
            from agent.langgraph_nodes.followup_node import followup_node
            from agent.langgraph_nodes.transition_node import transition_node
            from agent.langgraph_nodes.review_node import review_node
            from agent.langgraph_nodes.completion_node import completion_node
            
            nodes = {
                "greeting": greeting_node,
                "question": question_node,
                "evaluation": evaluation_node,
                "follow_up": followup_node,
                "transition": transition_node,
                "review": review_node,
                "completion": completion_node
            }
            
            logger.info(f"Created {len(nodes)} LangGraph nodes")
            return nodes
            
        except Exception as e:
            logger.error(f"Node creation failed: {e}")
            return {}
    
    def _add_edges(self, workflow: StateGraph):
        """Define edge routing logic"""
        try:
            # Greeting node routing
            workflow.add_conditional_edges(
                "greeting",
                self._route_from_greeting,
                {
                    "question": "question",
                    "greeting": "greeting"  # Stay in greeting if not ready
                }
            )
            
            # Question node always goes to evaluation
            workflow.add_edge("question", "evaluation")
            
            # Evaluation node conditional routing
            workflow.add_conditional_edges(
                "evaluation",
                self._route_from_evaluation,
                {
                    "follow_up": "follow_up",
                    "question": "question",
                    "transition": "transition",
                    "review": "review"
                }
            )
            
            # Follow-up always goes back to evaluation
            workflow.add_edge("follow_up", "evaluation")
            
            # Transition routing
            workflow.add_conditional_edges(
                "transition",
                self._route_from_transition,
                {
                    "question": "question",
                    "review": "review"
                }
            )
            
            # Review node routing
            workflow.add_conditional_edges(
                "review",
                self._route_from_review,
                {
                    "review": "review",  # Stay for modifications
                    "completion": "completion"
                }
            )
            
            # Completion is terminal
            workflow.add_edge("completion", "__end__")
            
            logger.info("LangGraph edges configured")
            
        except Exception as e:
            logger.error(f"Edge configuration failed: {e}")
            raise
    
    def _route_from_greeting(self, state: GraphState) -> str:
        """Route from greeting node based on user readiness"""
        try:
            next_node = state.get("next_node", "greeting")
            return next_node if next_node in ["question", "greeting"] else "greeting"
        except Exception as e:
            logger.error(f"Greeting routing failed: {e}")
            return "greeting"
    
    def _route_from_evaluation(self, state: GraphState) -> str:
        """Route from evaluation node based on response quality and rules"""
        try:
            next_node = state.get("next_node", "question")
            
            # Valid routing options from evaluation
            valid_routes = ["follow_up", "question", "transition", "review"]
            
            if next_node in valid_routes:
                return next_node
            else:
                logger.warning(f"Invalid route from evaluation: {next_node}")
                return "question"  # Default fallback
                
        except Exception as e:
            logger.error(f"Evaluation routing failed: {e}")
            return "question"
    
    def _route_from_transition(self, state: GraphState) -> str:
        """Route from transition node"""
        try:
            next_node = state.get("next_node", "question")
            
            # Check if all sections complete
            if state.get("session_complete", False):
                return "review"
            
            return "question" if next_node == "question" else "review"
            
        except Exception as e:
            logger.error(f"Transition routing failed: {e}")
            return "question"
    
    def _route_from_review(self, state: GraphState) -> str:
        """Route from review node"""
        try:
            next_node = state.get("next_node", "review")
            
            if next_node == "completion":
                return "completion"
            else:
                return "review"  # Stay in review for modifications
                
        except Exception as e:
            logger.error(f"Review routing failed: {e}")
            return "review"
    
    async def execute_workflow(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the LangGraph workflow"""
        try:
            if not self.graph:
                self.build_graph()
            
            # Convert to GraphState
            graph_state = GraphState(**initial_state)
            
            logger.info("Executing LangGraph workflow", 
                       session_id=graph_state.get("session_id"),
                       user_input=graph_state.get("user_input", "")[:50])
            
            # Execute workflow
            result = await self.graph.ainvoke(graph_state)
            
            logger.info("LangGraph workflow completed",
                       session_id=result.get("session_id"),
                       final_node=result.get("current_node", "unknown"))
            
            return result
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "error": f"Workflow execution failed: {e}",
                "agent_response": "I encountered an error processing your request. Please try again.",
                "requires_user_input": True,
                "session_complete": False
            }
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """Get current workflow status"""
        try:
            return {
                "graph_built": self.graph is not None,
                "nodes_count": len(self.nodes),
                "nodes_available": list(self.nodes.keys()),
                "status": "ready" if self.graph else "not_built"
            }
        except Exception as e:
            logger.error(f"Workflow status check failed: {e}")
            return {"status": "error", "error": str(e)}
    
    def rebuild_graph(self) -> bool:
        """Rebuild the LangGraph workflow"""
        try:
            self.graph = None
            self.nodes = {}
            self.build_graph()
            return True
        except Exception as e:
            logger.error(f"Graph rebuild failed: {e}")
            return False
    
    async def handle_error_recovery(self, state: GraphState, error: Exception) -> GraphState:
        """Handle workflow errors and provide recovery"""
        try:
            logger.error(f"Workflow error recovery triggered: {error}")
            
            # Update state with error info
            state["error_message"] = str(error)
            state["agent_response"] = "I encountered an issue. Let me try to help you continue."
            state["requires_user_input"] = True
            
            # Try to determine safe recovery point
            current_section = state.get("current_section", 1)
            current_criterion = state.get("current_criterion", "")
            
            if current_criterion:
                # We were in the middle of a question, go back to question node
                state["next_node"] = "question"
            else:
                # We were between sections, go to greeting for recovery
                state["next_node"] = "greeting"
            
            return state
            
        except Exception as recovery_error:
            logger.error(f"Error recovery failed: {recovery_error}")
            
            # Ultimate fallback
            state["agent_response"] = "I'm having trouble processing your request. Please try starting over."
            state["next_node"] = "greeting"
            state["requires_user_input"] = True
            
            return state


# Global workflow manager instance
workflow_manager = WorkflowManager()
