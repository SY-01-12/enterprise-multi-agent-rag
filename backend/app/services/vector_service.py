from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.documents import Document as LangchainDocument

from app.models.documents import Document
from app.models.document_chunks import DocumentChunk
from app.langchain_app.vectorstores.chroma import get_langchain_chroma


async def vectorize_document(document_id: int, db: AsyncSession) -> int:

    # 1. 查 Document
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 2. 查所有 chunk（按 chunk_index 排序）
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    chunks = result.scalars().all()

    if not chunks:
        raise HTTPException(status_code=400, detail="文档没有可向量化的内容")

    # 3. 转为 LangChain Document 列表
    lc_docs = [
        LangchainDocument(
            page_content=chunk.content,
            metadata={
                "chunk_index": chunk.chunk_index,
                "document_id": document_id,
            },
        )
        for chunk in chunks
    ]

    # 4. 获取 LangChain Chroma wrapper，调用 add_documents
    #    内部自动完成：Embedding → 写入 Chroma → 返回 ID 列表
    vectorstore = get_langchain_chroma(document.knowledge_base_id)
    vector_ids = vectorstore.add_documents(lc_docs)

    # 5. 将 vector_id 逐个写回 MySQL DocumentChunk
    for chunk, vector_id in zip(chunks, vector_ids):
        chunk.vector_id = vector_id

    await db.commit()

    return len(vector_ids)
