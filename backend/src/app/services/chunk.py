from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from app.models.document_chunks import DocumentChunk

# 每批插入的 chunk 数量（超大文件分批次处理）
BATCH_SIZE = 200


async def save_chunks(
    document_id: int,
    chunks: list,
    db: AsyncSession,
) -> int:

    # 1. 删除旧 chunks
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )

    # 2. 批量保存新 chunks
    buffer: list[DocumentChunk] = []
    for chunk in chunks:
        buffer.append(DocumentChunk(
            document_id=document_id,
            chunk_index=chunk.metadata.get("chunk_index", 0),
            content=chunk.page_content,
        ))

        # 每 BATCH_SIZE 个 chunk 提交一次，并重置 buffer
        if len(buffer) >= BATCH_SIZE:
            db.add_all(buffer)
            await db.commit()
            buffer = []
    # 提交最后剩余的 chunk
    if buffer:
        db.add_all(buffer)
        await db.commit()

    return len(chunks)
