import json
import sqlite3
from typing import Optional, Dict, Any
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from src.config import DB_PATH

@tool
def request_action_confirmation(
    action_type: str, 
    ticket_or_order_id: str, 
    reason: str, 
    metadata: Optional[Dict[str, Any]] = None,
    config: Optional[RunnableConfig] = None
) -> str:
    """
    Use this tool when preparing any state-changing action (escalate ticket, grant credit, cancel order).
    This tool pauses the agent and asks the human user for approval.
    """
    account_id = (config or {}).get("configurable", {}).get("account_id", "UNKNOWN")
    
    payload = {
        "status": "PENDING_CONFIRMATION",
        "action_type": action_type,
        "target_id": ticket_or_order_id,
        "reason": reason,
        "account_id": account_id,
        "metadata": metadata or {}
    }
    return json.dumps(payload)


def execute_confirmed_action(action_type: str, target_id: str, account_id: str, reason: str, metadata: Dict[str, Any]) -> str:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Check for both "escalate_ticket" and "escalate"
        if action_type in ["escalate_ticket", "escalate"]:
            cursor.execute(
                "UPDATE tickets SET status = 'ESCALATED', priority = 'P1' WHERE ticket_id = ?",
                (target_id,)
            )
            conn.commit()
            return f"✅ Ticket {target_id} has been formally escalated to P1 in the database."
            
        # Check for both "cancel_order" and "cancel"
        elif action_type in ["cancel_order", "cancel"]:
            cursor.execute(
                "UPDATE orders SET status = 'CANCELLED' WHERE order_id = ?",
                (target_id,)
            )
            conn.commit()
            fee = (metadata or {}).get("cancellation_fee_inr", 0)
            return f"✅ Order {target_id} has been marked as CANCELLED in database. Applied fee: ₹{fee}."

        # Check for both "grant_credit" and "credit"
        elif action_type in ["grant_credit", "credit"]:
            amount = (metadata or {}).get("credit_amount_inr", 0)
            return f"✅ Service credit of ₹{amount} has been logged and issued to account {account_id}."

        return f"Action {action_type} executed successfully on {target_id}."
    except Exception as e:
        return f"Database execution error: {str(e)}"
    finally:
        conn.close()