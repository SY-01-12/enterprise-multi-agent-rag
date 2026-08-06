from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# Agent 顶层状态，编译时注入 checkpointer 后按 thread_id 自动持久化
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: int
    kb_id: int | None
    remaining_steps: int
