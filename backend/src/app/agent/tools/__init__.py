from app.agent.tools.datetime import current_time
from app.agent.tools.image_gen import generate_image
from app.agent.tools.memory import remember, recall, forget
from app.agent.tools.rag import make_rag_tool

# RAG Agent 和 General Agent 共享的基础工具（记忆）
BASE_TOOLS = [remember, recall, forget]
# 只有 General Agent 持有的工具（时间、图片等通用任务）
GENERAL_EXTRA_TOOLS = [current_time, generate_image]

__all__ = [
    "BASE_TOOLS",
    "GENERAL_EXTRA_TOOLS",
    "current_time",
    "generate_image",
    "remember",
    "recall",
    "forget",
    "make_rag_tool",
]
