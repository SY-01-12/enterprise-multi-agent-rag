import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SessionNotFound, Forbidden

logger = logging.getLogger(__name__)
from app.models.chat_sessions import ChatSession
from app.models.chat_messages import ChatMessage
from app.agent.memory.saver import get_async_checkpointer

# 创建会话 函数
async def create_session(
    db: AsyncSession,
    user_id: int,
    knowledge_base_id: int | None,
    title: str,
) -> ChatSession:
    session = ChatSession(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        title=title[:200],
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


# 按 ID 查找会话
async def get_session(
    db: AsyncSession,
    session_id: int,
    current_user_id: int,
) -> ChatSession:

    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    session = result.scalars().one_or_none()
    if not session:
        raise SessionNotFound()
    if session.user_id != current_user_id:
        raise Forbidden("无权限访问该聊天会话")
    return session


# 获取会话列表 函数
async def get_sessions_by_list(
    db: AsyncSession,
    user_id: int,
) -> list[ChatSession]:
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
    )
    return list(result.scalars().all())


# message 消息
# 保存 message（只写 MySQL）
async def save_message(
    db: AsyncSession,
    session_id: int,
    role: str,
    content: str,
) -> ChatMessage:

    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


# 获取历史消息（直接查询 MySQL）
async def get_history(
    db: AsyncSession,
    session_id: int,
) -> list[ChatMessage]:

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())


# 删除会话缓存
async def invalidate_history_cache(session_id: int) -> None:

    try:
        checkpointer = await get_async_checkpointer()
        checkpointer.delete_thread(str(session_id))
    except Exception:
        logger.debug("Checkpoint 清理失败（不影响主流程）", exc_info=True)
