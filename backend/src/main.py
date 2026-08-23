# python -m src.main

import uuid
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.agent.graph import app as agent_app

# ==========================================
# FastAPI Initialization
# ==========================================
app = FastAPI(title="ParcelPilot AI Support API", version="1.0")

# Allow Next.js frontend to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Next.js domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# Pydantic Models (Data Validation)
# ==========================================
class ChatRequest(BaseModel):
    message: str
    account_id: str
    thread_id: Optional[str] = None

class ActionConfirmationRequest(BaseModel):
    thread_id: str
    account_id: str
    tool_call_id: str
    is_confirmed: bool

class ChatResponse(BaseModel):
    response_text: str
    thread_id: str
    requires_action: bool = False
    action_payload: Optional[Dict[str, Any]] = None
    used_tools: Optional[List[Dict[str, str]]] = []

# ==========================================
# Helper Functions
# ==========================================
def extract_text_content(content: Any) -> str:
    """Safely extracts clean string content and strips out internal reasoning blocks."""
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                # Ignore internal thinking/reasoning blocks
                if part.get("type") == "reasoning_content":
                    continue
                if "text" in part:
                    text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)
        return "\n".join(text_parts)
    return str(content)

def extract_recent_tools(messages: list) -> list:
    """Extracts tool outputs generated during the most recent user turn."""
    used_tools = []
    last_human_idx = next((i for i, msg in reversed(list(enumerate(messages))) if msg.type == 'human'), -1)
    
    if last_human_idx != -1:
        for msg in messages[last_human_idx:]:
            if msg.type == 'tool' and msg.name != "request_action_confirmation":
                used_tools.append({
                    "name": msg.name,
                    "content": str(msg.content)
                })
    return used_tools

# ==========================================
# API Endpoints
# ==========================================
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ParcelPilot AI Backend"}

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint. Processes the user's message through the LangGraph agent.
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    
    # Explicit RunnableConfig typing to satisfy Pylance
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "account_id": request.account_id # Invisible to the LLM, but tools can see it
        }
    }
    
    try:
        state = agent_app.invoke(
            {
                "messages": [HumanMessage(content=request.message)],
                "account_id": request.account_id
            },
            config=config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    last_message = state["messages"][-1]
    used_tools = extract_recent_tools(state["messages"])
    
    # Check for Action Confirmation (Requirement #4)
    tool_calls = getattr(last_message, "tool_calls", None)
    if tool_calls:
        for tool_call in tool_calls:
            if tool_call["name"] == "request_action_confirmation":
                return ChatResponse(
                    response_text="I have prepared this action for you. Please confirm to proceed:",
                    thread_id=thread_id,
                    requires_action=True,
                    action_payload={
                        "tool_call_id": tool_call["id"],
                        "details": tool_call["args"]  # Includes your new metadata field!
                    },
                    used_tools=used_tools
                )
                
    return ChatResponse(
        response_text=extract_text_content(last_message.content),
        thread_id=thread_id,
        requires_action=False,
        used_tools=used_tools
    )

@app.post("/confirm_action", response_model=ChatResponse)
def confirm_action_endpoint(request: ActionConfirmationRequest):
    """
    Endpoint called when the user clicks 'Confirm' or 'Cancel' on the frontend UI.
    """
    # Explicit RunnableConfig typing to satisfy Pylance
    config: RunnableConfig = {
        "configurable": {
            "thread_id": request.thread_id,
            "account_id": request.account_id 
        }
    }
    
    status_msg = (
        "Action confirmed by user. Proceed to finalize." 
        if request.is_confirmed 
        else "Action CANCELLED by user. Stop and inform the user."
    )
    
    tool_message = ToolMessage(
        tool_call_id=request.tool_call_id,
        content=status_msg
    )
    
    try:
        state = agent_app.invoke(
            {
                "messages": [tool_message],
                "account_id": request.account_id
            },
            config=config
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    last_message = state["messages"][-1]
    used_tools = extract_recent_tools(state["messages"])
    
    return ChatResponse(
        response_text=extract_text_content(last_message.content),
        thread_id=request.thread_id,
        requires_action=False,
        used_tools=used_tools
    )
    
    
# ==========================================
# Server Entrypoint
# ==========================================
if __name__ == "__main__":
    import uvicorn
    # Allows running directly via: python -m src.main
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)