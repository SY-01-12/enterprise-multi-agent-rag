from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.schema.chat import ChatRequest, MessageResponse, ModelListResponse, ModelItem
from app.services.chat import ask_question_stream
from app.services.history import get_history, get_session, get_sessions_by_list, invalidate_history_cache
from app.core.config import get_settings

router = APIRouter(
    prefix="/api/chat",
    tags=["聊天"],
)

# 历史消息接口
@router.get("/history/{session_id}",response_model=list[MessageResponse],summary="查看聊天历史")
async def chat_history(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 先验证会话存在且属于当前用户
    await get_session(db, session_id, current_user.id)
    messages = await get_history(db, session_id)
    return [
        MessageResponse(role=msg.role, content=msg.content)
        for msg in messages
    ]

# 流式问答接口
@router.post("/stream", summary="RAG 流式问答（SSE）")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    return StreamingResponse(
        ask_question_stream(
            db=db,
            current_user=current_user,
            knowledge_base_id=request.knowledge_base_id,
            question=request.question,
            session_id=request.session_id,
            model=request.model,
            mode=request.mode,
        ),
        # 指定 SSE 媒体类型
        media_type="text/event-stream",
    )

# 会话删除接口
@router.delete("/sessions/{session_id}", summary="删除聊天会话")
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定会话及其所有消息。"""
    session = await get_session(db, session_id, current_user.id)
    await db.delete(session)
    await db.commit()
    await invalidate_history_cache(session_id)
    return {"message": "会话已删除"}

# 模型列表接口
@router.get("/models", response_model=ModelListResponse, summary="获取可用模型列表")
async def list_models():
    """返回所有可用的 LLM 模型（百炼 + Ollama）。"""
    settings = get_settings()

    models: list[ModelItem] = []

    #  百炼模型
    bailian_names = ["qwen-turbo", "qwen-plus", "qwen-max"]
    if settings.BASE_MODEL and settings.BASE_MODEL not in bailian_names:
        bailian_names.append(settings.BASE_MODEL)

    for name in bailian_names:
        models.append(ModelItem(
            name=f"bailian:{name}",
            label=f"百炼 - {name}",
            provider="bailian",
        ))

    #  Ollama 模型
    if settings.OLLAMA_MODEL:
        models.append(ModelItem(
            name=f"ollama:{settings.OLLAMA_MODEL}",
            label=f"Ollama - {settings.OLLAMA_MODEL}",
            provider="ollama",
        ))

    return ModelListResponse(models=models, default=f"bailian:{settings.BASE_MODEL}")


# 会话列表接口
@router.get("/sessions", summary="获取聊天会话列表")
async def chat_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的所有聊天会话（按时间倒序）。"""
    sessions = await get_sessions_by_list(db, current_user.id)
    return [
        {
            "id": s.id,
            "title": s.title,
            "knowledge_base_id": s.knowledge_base_id,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]
