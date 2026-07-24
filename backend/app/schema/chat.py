"""聊天相关 Pydantic 模型。"""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求。

    第一次聊天不需要 session_id，系统会自动创建；
    续接会话时传入 session_id 以保持上下文。
    """

    knowledge_base_id: int = Field(..., description="知识库 ID")
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="用户问题，最长 2000 字符",
    )
    session_id: int | None = Field(
        default=None,
        description="聊天会话 ID，可选。不传则自动创建新会话",
    )


class ChatResponse(BaseModel):
    """聊天响应。"""

    answer: str = Field(..., description="AI 回答")
    sources: list[str] = Field(
        default_factory=list,
        description="引用来源（文档名列表）",
    )
    session_id: int = Field(..., description="聊天会话 ID（可用于续接对话）")


class MessageResponse(BaseModel):
    """单条聊天消息。"""

    role: str = Field(..., description="user 或 assistant")
    content: str = Field(..., description="消息内容")
