from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.documents import Document
from app.models.document_chunks import DocumentChunk
from app.langchain_app.search.elasticsearch import index_chunks


async def index_document_chunks(document_id: int, db: AsyncSession) -> int:
    """将文档的所有 chunk 批量写入 Elasticsearch。

    流程：
    1. 验证 Document 存在
    2. 查询所有 DocumentChunk（按 chunk_index 排序）
    3. 转为 ES 文档格式，通过 bulk API 批量写入
    4. 返回成功写入数量
    """
    # 1. 验证文档存在
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 2. 查询所有 chunks
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()

    if not chunks:
        return 0

    # 3. 转为 ES 文档格式
    es_docs = [
        {
            "chunk_id": chunk.id,
            "document_id": document_id,
            "content": chunk.content,
        }
        for chunk in chunks
    ]

    # 4. bulk 批量写入 ES
    es_count = index_chunks(es_docs)

    return es_count
