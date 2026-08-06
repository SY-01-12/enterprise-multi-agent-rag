import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.documents import Document
from app.rag.loader.factory import load_document
from app.rag.splitter.text import split_documents
from app.services.chunk import save_chunks
from app.services.vector import vectorize_document
from app.services.search import index_document_chunks

logger = logging.getLogger(__name__)


async def process_document(document_id: int, db: AsyncSession) -> dict:
    """完整处理一个文档：加载 → 切分 → 写 MySQL → 向量化 → ES 索引 → 标记完成。"""

    #  1. 查询 Document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")
   
    #  2. 加载文件
    docs = load_document(document.file_path)
    if not docs:
        raise HTTPException(status_code=400, detail="文档内容为空或格式不支持")

    #  3. 切分文本
    chunks = split_documents(docs)
    if not chunks:
        raise HTTPException(status_code=400, detail="文档没有可切分的内容")

    #  4. 写入 MySQL
    chunk_count = await save_chunks(document_id, chunks, db)

    #  5. 向量化：Embedding → Chroma → vector_id 回写 MySQL
    vector_count = await vectorize_document(document_id, db)

    #  6. ES 全文索引（可选，失败不影响主流程）
    es_count = 0
    try:
        es_count = await index_document_chunks(document_id, db)
    except Exception:
        logger.warning("ES 索引失败（不影响主流程）", exc_info=True)

    #  7. 标记完成
    document.status = "processed"
    await db.commit()

    return {
        "document_id": document_id,
        "chunks": chunk_count,
        "vectors": vector_count,
        "es_indexed": es_count,
    }
