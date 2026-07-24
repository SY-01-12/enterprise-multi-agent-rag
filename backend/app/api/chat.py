"""聊天 API — RAG 问答接口。"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.schema.chat import ChatRequest, MessageResponse
from app.services.chat_service import ask_question_stream
from app.services.chat_history_service import get_history, get_session_or_404, get_sessions_by_user

router = APIRouter(
    prefix="/api/chat",
    tags=["聊天"],
)


@router.get(
    "/history/{session_id}",
    response_model=list[MessageResponse],
    summary="查看聊天历史",
)
async def chat_history(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定会话的完整聊天记录（按时间排序）。"""
    # 先验证会话存在且属于当前用户
    await get_session_or_404(db, session_id, current_user.id)
    messages = await get_history(db, session_id)
    return [
        MessageResponse(role=msg.role, content=msg.content)
        for msg in messages
    ]


@router.post("/stream", summary="RAG 流式问答（SSE）")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """基于知识库内容流式回答问题（Server-Sent Events）。

    与 /ask 逻辑相同，但通过 SSE 逐 token 推送回答内容，
    前端可实现类似 ChatGPT 的打字机效果。

    SSE 事件格式：
        data: {"session_id": 1}
        data: {"token": "员"}
        data: {"token": "工"}
        ...
        data: {"done": true}
    """
    return StreamingResponse(
        ask_question_stream(
            db=db,
            current_user=current_user,
            knowledge_base_id=request.knowledge_base_id,
            question=request.question,
            session_id=request.session_id,
        ),
        media_type="text/event-stream",
    )


@router.delete("/sessions/{session_id}", summary="删除聊天会话")
async def delete_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除指定会话及其所有消息。"""
    session = await get_session_or_404(db, session_id, current_user.id)
    await db.delete(session)
    await db.commit()
    return {"message": "会话已删除"}


@router.get("/sessions", summary="获取聊天会话列表")
async def chat_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的所有聊天会话（按时间倒序）。"""
    sessions = await get_sessions_by_user(db, current_user.id)
    return [
        {
            "id": s.id,
            "title": s.title,
            "knowledge_base_id": s.knowledge_base_id,
            "created_at": s.created_at.isoformat(),
        }
        for s in sessions
    ]
