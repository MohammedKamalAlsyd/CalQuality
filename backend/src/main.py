# python -m src.main

import uuid
import json
import sqlite3
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig

from src.agent.graph import app as agent_app
from src.tools.actions import execute_confirmed_action
from src.config import DB_PATH, DATASET_SNAPSHOT_TIME

app = FastAPI(title="ParcelPilot AI Support API", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for pending action details per thread
PENDING_ACTIONS: Dict[str, Dict[str, Any]] = {}

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

def extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "reasoning_content":
                    continue
                if "text" in part:
                    text_parts.append(part["text"])
            elif isinstance(part, str):
                text_parts.append(part)
        return "\n".join(text_parts)
    return str(content)

def extract_recent_tools(messages: list) -> list:
    used_tools = []
    last_human_idx = next((i for i, msg in reversed(list(enumerate(messages))) if msg.type == 'human'), -1)
    if last_human_idx != -1:
        for msg in messages[last_human_idx:]:
            if msg.type == 'tool' and msg.name != "request_action_confirmation":
                used_tools.append({"name": msg.name, "content": str(msg.content)})
    return used_tools

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "snapshot_reference_time": DATASET_SNAPSHOT_TIME
    }

@app.get("/ops/anomalies")
def get_ops_anomalies():
    """
    Problem 1: Proactive anomaly detection endpoint with schema-safe column resolution.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    anomalies = []
    
    try:
        # Inspect columns for 'orders' table
        cursor.execute("PRAGMA table_info(orders)")
        order_cols = {col["name"].lower(): col["name"] for col in cursor.fetchall()}
        
        status_col = order_cols.get("status", "status")
        carrier_col = order_cols.get("carrier", "carrier")
        account_col = order_cols.get("account_id", "account_id")

        # 1. Scan for carrier delivery/pickup issues
        if carrier_col in order_cols and status_col in order_cols:
            query = f"""
                SELECT {carrier_col} AS carrier, 
                       COUNT(*) AS failed_count, 
                       GROUP_CONCAT(DISTINCT {account_col}) AS accounts
                FROM orders 
                WHERE UPPER({status_col}) LIKE '%DELAY%' 
                   OR UPPER({status_col}) LIKE '%MISS%' 
                   OR UPPER({status_col}) LIKE '%FAIL%'
                   OR UPPER({status_col}) LIKE '%EXCEPTION%'
                GROUP BY {carrier_col}
                HAVING COUNT(*) > 0
            """
            cursor.execute(query)
            for row in cursor.fetchall():
                anomalies.append({
                    "key": f"carrier_{row['carrier']}",
                    "type": f"Carrier Route Instability ({row['carrier']})",
                    "severity": "high",
                    "affected_accounts": str(row['accounts']).split(",") if row['accounts'] else [],
                    "description": f"{row['failed_count']} orders impacted by delays or exceptions with carrier {row['carrier']}.",
                    "suggested_action": "Notify affected accounts and initiate preemptive credit evaluation."
                })

        # Inspect columns for 'tickets' table
        cursor.execute("PRAGMA table_info(tickets)")
        ticket_cols = {col["name"].lower(): col["name"] for col in cursor.fetchall()}
        
        t_id = ticket_cols.get("ticket_id", "ticket_id")
        t_acc = ticket_cols.get("account_id", "account_id")
        t_status = ticket_cols.get("status", "status")
        
        # Priority can be named 'priority', 'severity', or 'tier'
        t_pri = (
            ticket_cols.get("priority") 
            or ticket_cols.get("severity") 
            or ticket_cols.get("urgency") 
            or ticket_cols.get("level")
        )
        
        # Subject / Issue description column
        t_subj = (
            ticket_cols.get("subject") 
            or ticket_cols.get("issue") 
            or ticket_cols.get("description") 
            or ticket_cols.get("title") 
            or t_id
        )

        # 2. Scan for high-severity or open tickets
        if t_pri and t_status:
            cursor.execute(f"""
                SELECT {t_id} AS ticket_id, 
                       {t_acc} AS account_id, 
                       {t_subj} AS subject,
                       {t_pri} AS priority
                FROM tickets 
                WHERE (UPPER({t_pri}) LIKE '%P1%' OR UPPER({t_pri}) LIKE '%HIGH%' OR UPPER({t_pri}) LIKE '%CRITICAL%')
                  AND UPPER({t_status}) NOT LIKE '%CLOSE%'
                  AND UPPER({t_status}) NOT LIKE '%RESOLV%'
            """)
            for row in cursor.fetchall():
                anomalies.append({
                    "key": f"sla_{row['ticket_id']}",
                    "type": f"Urgent Open Ticket ({row['priority']})",
                    "severity": "high",
                    "affected_accounts": [row['account_id']],
                    "description": f"Ticket {row['ticket_id']}: '{row['subject']}' is unclosed.",
                    "suggested_action": "Reassign to senior tier support manager immediately."
                })
        else:
            # Fallback if no priority column exists: flag open tickets
            cursor.execute(f"""
                SELECT {t_id} AS ticket_id, {t_acc} AS account_id, {t_subj} AS subject
                FROM tickets
                WHERE UPPER({t_status}) NOT LIKE '%CLOSE%' AND UPPER({t_status}) NOT LIKE '%RESOLV%'
                LIMIT 5
            """)
            for row in cursor.fetchall():
                anomalies.append({
                    "key": f"open_{row['ticket_id']}",
                    "type": "Open Support Ticket",
                    "severity": "medium",
                    "affected_accounts": [row['account_id']],
                    "description": f"Ticket {row['ticket_id']}: '{row['subject']}' is pending resolution.",
                    "suggested_action": "Review ticket details against customer SLA."
                })

    except Exception as e:
        print(f"Error in anomaly scanner: {e}")
    finally:
        conn.close()

    return {"snapshot_time": DATASET_SNAPSHOT_TIME, "anomalies": anomalies}

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint. Processes the user's message through the LangGraph agent.
    """
    thread_id = request.thread_id or str(uuid.uuid4())
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "account_id": request.account_id
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
    
    tool_calls = getattr(last_message, "tool_calls", None)
    if tool_calls:
        for tool_call in tool_calls:
            if tool_call["name"] == "request_action_confirmation":
                # Store pending action payload for execution
                PENDING_ACTIONS[tool_call["id"]] = tool_call["args"]
                return ChatResponse(
                    response_text="I have prepared this state-changing action. Please review and confirm to proceed:",
                    thread_id=thread_id,
                    requires_action=True,
                    action_payload={
                        "tool_call_id": tool_call["id"],
                        "details": tool_call["args"]
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
    
    execution_result_msg = ""
    
    if request.is_confirmed:
        action_args = PENDING_ACTIONS.get(request.tool_call_id, {})
        # Perform REAL database mutation
        execution_result_msg = execute_confirmed_action(
            action_type=action_args.get("action_type", ""),
            target_id=action_args.get("ticket_or_order_id", ""),
            account_id=request.account_id,
            reason=action_args.get("reason", ""),
            metadata=action_args.get("metadata", {})
        )
        status_msg = f"User confirmed action. Execution Result: {execution_result_msg}"
    else:
        status_msg = "User REJECTED the action. Inform the user that the operation was canceled."
    
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)