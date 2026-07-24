from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True,index=True)

    username: Mapped[str] = mapped_column(String(50),unique=True,nullable=False,index=True)

    email: Mapped[str] = mapped_column(String(100),unique=True,nullable=False,index=True)

    password_hash: Mapped[str] = mapped_column(String(255),nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean,default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime,default=func.now())

    updated_at: Mapped[datetime] = mapped_column(DateTime,default=func.now(),onupdate=func.now())

    # 一个用户拥有多个知识库
    """
    cascade = 'all, delete-orphan': 删除父记录时，所有关联的子记录自动删除
    """
    knowledge_bases = relationship("KnowledgeBase",back_populates="owner",cascade="all, delete-orphan")

    # 一个用户拥有多个聊天会话
    chat_sessions = relationship("ChatSession",back_populates="user",cascade="all, delete-orphan")