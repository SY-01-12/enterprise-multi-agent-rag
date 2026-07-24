"""聊天历史服务：Session 管理 + Message 管理。"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat_sessions import ChatSession
from app.models.chat_messages import ChatMessage


# ══════════════════════════════════════════════════════
# Session 管理
# ══════════════════════════════════════════════════════

async def create_session(
    db: AsyncSession,
    user_id: int,
    knowledge_base_id: int,
    title: str,
) -> ChatSession:
    """创建新的聊天会话。

    Args:
        db: 数据库会话
        user_id: 用户 ID
        knowledge_base_id: 知识库 ID
        title: 会话标题（通常取第一个问题的前若干字）

    Returns:
        新创建的 ChatSession 对象
    """
    session = ChatSession(
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        title=title[:200],  # 截断至字段长度
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def get_session(
    db: AsyncSession,
    session_id: int,
) -> ChatSession | None:
    """根据 ID 查询聊天会话。"""
    result = await db.execute(
        select(ChatSession).where(ChatSession.id == session_id)
    )
    return result.scalars().one_or_none()


async def get_session_or_404(
    db: AsyncSession,
    session_id: int,
    current_user_id: int,
) -> ChatSession:
    """查询会话，不存在或不属于当前用户时抛出 404/403。"""
    session = await get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="聊天会话不存在")
    if session.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="无权限访问该聊天会话")
    return session


async def get_sessions_by_user(
    db: AsyncSession,
    user_id: int,
) -> list[ChatSession]:
    """获取用户的所有聊天会话（按创建时间倒序）。"""
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.created_at.desc())
    )
    return list(result.scalars().all())


# ══════════════════════════════════════════════════════
# Message 管理
# ══════════════════════════════════════════════════════

async def save_message(
    db: AsyncSession,
    session_id: int,
    role: str,
    content: str,
) -> ChatMessage:
    """保存一条聊天消息。

    Args:
        db: 数据库会话
        session_id: 会话 ID
        role: 角色（"user" 或 "assistant"）
        content: 消息内容

    Returns:
        新创建的 ChatMessage 对象
    """
    message = ChatMessage(
        session_id=session_id,
        role=role,
        content=content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def get_history(
    db: AsyncSession,
    session_id: int,
) -> list[ChatMessage]:
    """获取指定会话的所有消息（按创建时间正序）。"""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return list(result.scalars().all())
