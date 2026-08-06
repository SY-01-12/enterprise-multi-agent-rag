from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document_chunks import DocumentChunk
from app.rag.retriever.elasticsearch import index_chunks


async def index_document_chunks(document_id: int, db: AsyncSession) -> int:

    # 1. 查询所有 chunks
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()

    if not chunks:
        return 0

    # 2. 组装待索引数据
    es_docs = [
        {
            "chunk_id": chunk.id,
            "document_id": document_id,
            "content": chunk.content,
        }
        for chunk in chunks
    ]
    # 3. bulk 批量写入 ES（传入 document_id 做增量更新）
    es_count = index_chunks(es_docs, document_id=document_id)

    return es_count
