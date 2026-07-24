from datetime import datetime
from sqlalchemy import String,DateTime,ForeignKey,func, Text
from sqlalchemy.orm import Mapped,mapped_column,relationship

from app.db.base import Base


class ChatMessage(Base):

    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True,index=True)

    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"),nullable=False)

    role: Mapped[str] = mapped_column(String(20),nullable=False)

    content: Mapped[str] = mapped_column(Text,nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime,default=func.now())

    # 所属会话
    session = relationship("ChatSession",back_populates="messages")