from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.documents import Document
from app.models.document_chunks import DocumentChunk
from app.langchain_app.loaders.factory import LOADER_MAP
from app.langchain_app.splitters.text_splitter import split_documents

# 每批插入的 chunk 数量（超大文件分批次处理）
BATCH_SIZE = 200

#上传文件 → 查数据库找记录 → 根据格式选加载器 → 提取文字 → 切成小块 → 删旧数据 → 分批存新数据 → 向量化(Embedding+Chroma) → ES全文索引 → 标记完成
async def process_document(document_id: int, db: AsyncSession) -> dict:
    # 1. 查询 Document 记录
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 2. 获取对应 Loader
    loader = LOADER_MAP.get(document.file_type)
    if not loader:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: .{document.file_type}",
        )

    # 3. Loader 加载
    docs = loader(document.file_path)
    if not docs:
        raise HTTPException(status_code=400, detail="文档内容为空")

    # 4. Splitter 切分
    chunks = split_documents(docs)

    # 5. 删除旧 chunks（防止重复处理产生重复数据）
    #如果这个文档之前已经处理过一次了（比如用户重新上传了同名文件），先把旧数据清掉，避免数据重复。
    await db.execute(
        delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
    )

    # 6. 批量保存新 chunks
    db_chunks = []
    for chunk in chunks:
        db_chunk = DocumentChunk(
            document_id=document_id,
            chunk_index=chunk.metadata.get("chunk_index", 0),
            content=chunk.page_content,
        )
        db_chunks.append(db_chunk)

        # 分批 commit，防止超大文件一次性占用过多内存
        if len(db_chunks) >= BATCH_SIZE:
            db.add_all(db_chunks)
            await db.commit()
            db_chunks = []

    # 提交剩余批次
    if db_chunks:
        db.add_all(db_chunks)
        await db.commit()

    # 7. 向量化 → Chroma（Embedding + 写入向量库 + 更新 MySQL vector_id）
    from app.services.vector_service import vectorize_document
    vector_count = await vectorize_document(document_id, db)

    # 8. ES 全文索引（可选，失败不影响主流程）
    try:
        from app.services.search_service import index_document_chunks
        es_count = await index_document_chunks(document_id, db)
    except Exception:
        es_count = 0

    # 9. 更新文档状态
    document.status = "processed"
    await db.commit()

    return {
        "document_id": document_id,
        "chunks": len(chunks),
        "vectors": vector_count,
        "es_indexed": es_count,
    }
