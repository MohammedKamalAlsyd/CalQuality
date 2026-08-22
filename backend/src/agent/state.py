from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # The list of messages (chat history + agent thoughts)
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # The current user's context (e.g., "ACCT-001" or "INTERNAL_OPS")
    account_id: str