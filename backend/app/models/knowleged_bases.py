from datetime import datetime
from sqlalchemy import String,DateTime,ForeignKey,func, Text
from sqlalchemy.orm import Mapped,mapped_column,relationship

from app.db.base import Base


class KnowledgeBase(Base):

    __tablename__ = "knowledge_bases"

    id: Mapped[int] = mapped_column(primary_key=True,index=True)

    name: Mapped[str] = mapped_column(String(100),nullable=False)

    description: Mapped[str | None] = mapped_column(Text,nullable=True)

    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"),nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime,default=func.now())

    # 所属用户
    owner = relationship("User",back_populates="knowledge_bases" )

    # 一个知识库包含多个文档
    documents = relationship("Document",back_populates="knowledge_base",cascade="all, delete-orphan")

    # 一个知识库对应多个聊天
    chat_sessions = relationship("ChatSession",back_populates="knowledge_base")