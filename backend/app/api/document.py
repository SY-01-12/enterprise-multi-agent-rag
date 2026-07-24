from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.schema.document import DocumentResponse, ProcessResponse
from app.services.document_service import upload_document
from app.services.chunk_service import process_document

router = APIRouter(
    prefix="/api/document",
    tags=["文档"],
)


@router.post("/upload", response_model=DocumentResponse, summary="上传文档")
async def upload(
    knowledge_base_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    document = await upload_document(file, knowledge_base_id, current_user, db)
    return document

@router.post("/process/{document_id}", response_model=ProcessResponse, summary="处理文档")
async def process(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    result = await process_document(document_id, db)
    return result