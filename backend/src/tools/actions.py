import json
from typing import Optional, Dict, Any
from langchain_core.tools import tool

@tool
def request_action_confirmation(
    action_type: str, 
    ticket_or_order_id: str, 
    reason: str, 
    account_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Use this tool when you need to perform a state-changing action like:
    - Escalate a ticket (action_type: 'escalate_ticket')
    - Grant a service credit (action_type: 'grant_credit')
    - Cancel an order (action_type: 'cancel_order')
    
    This tool prepares the action and pauses the system to ask the human user for confirmation.
    
    Args:
        action_type: One of 'escalate_ticket', 'grant_credit', or 'cancel_order'.
        ticket_or_order_id: The ID of the affected order or ticket (e.g., 'ORD-2002', 'TKT-501').
        reason: Explanation of why this action is being taken based on policies/agreements.
        account_id: The account ID performing or subject to the action.
        metadata: Key-value pairs with action-specific calculations or parameters.
            - For 'grant_credit': include 'credit_amount_inr' (int) and 'requires_manager_approval' (bool if > 1000).
            - For 'escalate_ticket': include 'severity' ('P1'|'P2'|'P3'), 'csm' (str), and 'sla_breached' (bool).
            - For 'cancel_order': include 'cancellation_fee_inr' (int) and 'order_status' (str).
    """
    
    payload = {
        "status": "PENDING_CONFIRMATION",
        "action_type": action_type,
        "target_id": ticket_or_order_id,
        "reason": reason,
        "account_id": account_id,
        "metadata": metadata or {}
    }
    
    return json.dumps(payload)