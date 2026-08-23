import os
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver

from src.clients.bedrock import bedrock
from src.tools.retriever import search_documents
from src.tools.database import query_structured_data
from src.tools.actions import request_action_confirmation
from src.agent.state import AgentState
from src.agent.prompts import SYSTEM_PROMPT
from src.config import DATASET_SNAPSHOT_TIME, CURRENCY

tools = [search_documents, query_structured_data, request_action_confirmation]
MODEL_ID = os.getenv("GENERATION_MODEL_ID", "meta.llama3-70b-instruct-v1:0")

llm = ChatBedrockConverse(
    client=bedrock,
    model=MODEL_ID,
    temperature=0
)
llm_with_tools = llm.bind_tools(tools)

def agent_node(state: AgentState):
    messages = state["messages"]
    account_id = state["account_id"]
    
    # Prepend dynamic system prompt containing reference snapshot time
    if not any(isinstance(m, SystemMessage) for m in messages):
        sys_msg = SystemMessage(
            content=SYSTEM_PROMPT.format(
                account_id=account_id,
                snapshot_time=DATASET_SNAPSHOT_TIME,
                currency=CURRENCY
            )
        )
        messages = [sys_msg] + list(messages)
        
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def should_continue(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    
    # Check if last_message is an AIMessage with tool_calls to satisfy Pylance
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            if tool_call["name"] == "request_action_confirmation":
                return "action_confirmation_pause"
        return "continue"
        
    return "end"

workflow = StateGraph(AgentState)
workflow.add_node("agent", agent_node)
workflow.add_node("action", ToolNode(tools))

workflow.set_entry_point("agent")

workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "continue": "action",
        "action_confirmation_pause": END,
        "end": END
    }
)
workflow.add_edge("action", "agent")

memory = MemorySaver()
app = workflow.compile(checkpointer=memory)