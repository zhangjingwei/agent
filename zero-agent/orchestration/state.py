"""
状态管理
"""

from typing import TypedDict, Annotated, Sequence, Dict, List, Any
from langchain_core.messages import BaseMessage


class AgentState(TypedDict):
    """Agent状态"""
    messages: Annotated[Sequence[BaseMessage], "add_messages"]
    session_id: str
    agent_id: str
    tool_calls: List[Dict[str, Any]]
    iteration_count: int
    max_iterations: int
    processing_time: float
    errors: List[str]
    metadata: Dict[str, Any]
