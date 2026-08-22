import os
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import HumanMessage, SystemMessage

from src.clients.bedrock import bedrock
from src.tools.retriever import search_documents
from src.tools.database import query_structured_data
from src.tools.actions import request_action_confirmation
from src.agent.state import AgentState
from src.agent.prompts import SYSTEM_PROMPT
from langgraph.checkpoint.memory import MemorySaver

# 1. Define Tools & Model
tools = [search_documents, query_structured_data, request_action_confirmation]
MODEL_ID = os.getenv("GENERATION_MODEL_ID", "meta.llama3-70b-instruct-v1:0")

# Wrap the provided Bedrock boto3 client so it supports tool calling
llm = ChatBedrockConverse(
    client=bedrock,
    model=MODEL_ID,
    temperature=0
)
llm_with_tools = llm.bind_tools(tools)

# 2. Node: The AI Reasoning Step
def agent_node(state: AgentState):
    messages = state["messages"]
    account_id = state["account_id"]
    
    # Inject the system prompt with the current account context if it's the first turn
    if not any(isinstance(m, SystemMessage) for m in messages):
        sys_msg = SystemMessage(content=SYSTEM_PROMPT.format(account_id=account_id))
        messages = [sys_msg] + list(messages)
        
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

# 3. Edge Logic: Should we use a tool or reply to user?
def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    
    # If the LLM called a tool, go to the tool node
    if last_message.tool_calls: # type: ignore
        # Check if it called the state-changing tool that requires confirmation
        for tool_call in last_message.tool_calls: # type: ignore
            if tool_call["name"] == "request_action_confirmation":
                return "action_confirmation_pause"
        return "continue"
        
    # Otherwise, end the turn and return to user
    return "end"

# 4. Build the Graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", agent_node)
workflow.add_node("action", ToolNode(tools)) # Standard tool execution

workflow.set_entry_point("agent")

# Add edges
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "action",
        "action_confirmation_pause": END, # PAUSE FOR HUMAN INTERVENTION
        "end": END
    }
)
workflow.add_edge("action", "agent")

# Compile the graph
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)