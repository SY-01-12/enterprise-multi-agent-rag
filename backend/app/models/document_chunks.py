from sqlalchemy import String,ForeignKey, Text, Integer
from sqlalchemy.orm import Mapped,mapped_column,relationship

from app.db.base import Base


class DocumentChunk(Base):

    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(primary_key=True,index=True)

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"),nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer,nullable=False)

    content: Mapped[str] = mapped_column(Text,nullable=False)

    vector_id: Mapped[str | None] = mapped_column(String(100),nullable=True)

    # 所属文档
    document = relationship("Document",back_populates="chunks")