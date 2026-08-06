from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.services.file_chat import ask_file_stream

router = APIRouter(
    prefix="/api/file",
    tags=["文件问答"],
)

# 上传文件并提问
@router.post("/ask", summary="上传文件并提问")
async def ask(
    file: UploadFile = File(..., description="上传的文件"),
    question: str = Form(..., description="用户问题"),
    session_id: int | None = Form(None, description="会话 ID，可选"),
    model: str | None = Form(None, description="模型名称，可选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

    return StreamingResponse(
        ask_file_stream(
            db=db,
            current_user=current_user,
            file=file,
            question=question,
            session_id=session_id,
            model=model,
        ),
        media_type="text/event-stream",
    )
