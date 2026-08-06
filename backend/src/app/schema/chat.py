from pydantic import BaseModel, Field


# 会话请求
class ChatRequest(BaseModel):

    knowledge_base_id: int = Field(default=0, description="知识库 ID，0 表示由 Supervisor 自动判断")
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
    model: str | None = Field(
        default=None,
        description="模型标识，如 bailian:qwen-turbo / ollama:qwen3.5:4b。不传使用默认模型",
    )
    mode: str | None = Field(
        default=None,
        description="Agent 模式：general（通用对话）/ rag（知识库检索）/ auto（自动调度）。不传自动判断",
    )


# 消息响应
class MessageResponse(BaseModel):
    role: str = Field(..., description="user 或 assistant")
    content: str = Field(..., description="消息内容")


# SSE 流式事件
class SSEEvent(BaseModel):
    """SSE 事件基类。"""

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json()}\n\n"


class SessionCreated(SSEEvent):
    session_id: int


class ToolCallStarted(SSEEvent):
    tool: str
    label: str = ""   # 中文显示名，前端优先使用
    input: str


class TokenGenerated(SSEEvent):
    token: str


class StreamDone(SSEEvent):
    done: bool = True


class StreamError(SSEEvent):
    error: str


class ImageGenerated(SSEEvent):
    url: str
    prompt: str


# 模型列表
class ModelItem(BaseModel):
    name: str = Field(..., description="模型标识（传参用），如 bailian:qwen-turbo")
    label: str = Field(..., description="前端展示名，如 百炼 - qwen-turbo")
    provider: str = Field(..., description="提供商：bailian / ollama")


class ModelListResponse(BaseModel):
    models: list[ModelItem] = Field(..., description="可用模型列表")
    default: str = Field(..., description="默认模型标识")
