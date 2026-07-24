from datetime import datetime
from sqlalchemy import String,DateTime,ForeignKey,func
from sqlalchemy.orm import Mapped,mapped_column,relationship

from app.db.base import Base


class ChatSession(Base):

    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True,index=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"),nullable=False)

    knowledge_base_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_bases.id"),nullable=True)

    title: Mapped[str | None] = mapped_column(String(200))

    created_at: Mapped[datetime] = mapped_column(DateTime,default=func.now())

    # 用户
    user = relationship("User",back_populates="chat_sessions")

    # 使用哪个知识库
    knowledge_base = relationship("KnowledgeBase",back_populates="chat_sessions")

    # 聊天消息
    messages = relationship("ChatMessage",back_populates="session",cascade="all, delete-orphan")