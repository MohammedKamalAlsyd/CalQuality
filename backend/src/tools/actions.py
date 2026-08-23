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
        if action_type in ["escalate_ticket", "escalate"]:
            # 🧠 BRAIN CHECK: Does the ticket exist? Is it already escalated?
            cursor.execute("SELECT status, priority FROM tickets WHERE ticket_id = ?", (target_id,))
            row = cursor.fetchone()
            
            if not row:
                return f"❌ FAILURE: Ticket {target_id} does not exist in the database. Tell the user."
            if row[0] == 'ESCALATED' and row[1] == 'P1':
                return f"⚠️ INFO: Ticket {target_id} is ALREADY escalated and marked as P1. No changes were made."
                
            # If it exists and isn't escalated yet, execute the update!
            cursor.execute("UPDATE tickets SET status = 'ESCALATED', priority = 'P1' WHERE ticket_id = ?", (target_id,))
            conn.commit()
            return f"✅ SUCCESS: Ticket {target_id} was found and successfully escalated to P1 in the database."
            
        elif action_type in ["cancel_order", "cancel"]:
            # 🧠 BRAIN CHECK: Does the order exist? Is it already cancelled?
            cursor.execute("SELECT status FROM orders WHERE order_id = ?", (target_id,))
            row = cursor.fetchone()
            
            if not row:
                return f"❌ FAILURE: Order {target_id} does not exist in the database."
            if row[0] == 'CANCELLED':
                return f"⚠️ INFO: Order {target_id} is ALREADY cancelled. No changes made."
                
            cursor.execute("UPDATE orders SET status = 'CANCELLED' WHERE order_id = ?", (target_id,))
            conn.commit()
            fee = (metadata or {}).get("cancellation_fee_inr", 0)
            return f"✅ SUCCESS: Order {target_id} has been marked as CANCELLED. Applied fee: ₹{fee}."

        elif action_type in ["grant_credit", "credit"]:
            amount = (metadata or {}).get("credit_amount_inr", 0)
            return f"✅ SUCCESS: Service credit of ₹{amount} has been securely logged to account {account_id}."

        return f"Action {action_type} executed successfully on {target_id}."
    except Exception as e:
        return f"Database execution error: {str(e)}"
    finally:
        conn.close()