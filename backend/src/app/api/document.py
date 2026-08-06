from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.models.documents import Document
from app.schema.document import DocumentResponse, ProcessResponse
from app.services.document import upload_document
from app.services.document_pipeline import process_document
from app.services.knowledge_base import require_owner

router = APIRouter(
    prefix="/api/document",
    tags=["文档"],
)

# 上传文档
@router.post("/upload", response_model=DocumentResponse, summary="上传文档")
async def upload(
    knowledge_base_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await upload_document(file, knowledge_base_id, current_user, db)
    return document

# 处理文档
@router.post("/process/{document_id}", response_model=ProcessResponse, summary="处理文档")
async def process(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 验证文档是否存在
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 仅 owner 可处理文档
    await require_owner(document.knowledge_base_id, current_user.id, db)

    result = await process_document(document_id, db)
    return result