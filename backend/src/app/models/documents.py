from datetime import datetime
from sqlalchemy import String,DateTime,ForeignKey,func
from sqlalchemy.orm import Mapped,mapped_column,relationship

from app.db.base import Base


class Document(Base):

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True,index=True)

    knowledge_base_id: Mapped[int] = mapped_column(ForeignKey("knowledge_bases.id"),nullable=False)

    filename: Mapped[str] = mapped_column(String(255),nullable=False)

    file_type: Mapped[str] = mapped_column(String(50))

    file_path: Mapped[str] = mapped_column(String(500))

    status: Mapped[str] = mapped_column(String(50),default="pending")

    created_at: Mapped[datetime] = mapped_column(DateTime,default=func.now())

    # 所属知识库
    knowledge_base = relationship("KnowledgeBase",back_populates="documents")

    # 一个文档包含多个切片
    chunks = relationship("DocumentChunk",back_populates="document",cascade="all, delete-orphan")