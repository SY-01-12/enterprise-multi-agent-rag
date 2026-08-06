import os
from pathlib import Path
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.documents import Document
from app.services.knowledge_base import require_owner

# 允许的文件类型
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt", "xlsx", "xlsm", "jpg", "jpeg", "png", "gif", "bmp", "webp"}
# 文件大小限制：50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

# 上传目录：基于项目根目录的绝对路径，避免工作目录不同导致路径漂移
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
UPLOAD_DIR = str(PROJECT_ROOT / "data" / "uploads")

# 上传文件
async def upload_document(
    file: UploadFile,
    knowledge_base_id: int,
    current_user: User,
    db: AsyncSession,
):
    # 1. 仅 owner 可上传文档
    await require_owner(knowledge_base_id, current_user.id, db)

    # 2. 检查文件是否为空
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件不能为空")

    # 3. 检查文件格式
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: .{ext}，仅支持: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 4. 检查文件大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件过大，最大支持 50MB")
    await file.seek(0)  # 重置文件指针

    # 5. 保存文件到磁盘
    kb_dir = os.path.join(UPLOAD_DIR, f"kb_{knowledge_base_id}")
    os.makedirs(kb_dir, exist_ok=True)
    file_path = os.path.join(kb_dir, file.filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # 6. 创建数据库记录
    document = Document(
        knowledge_base_id=knowledge_base_id,
        filename=file.filename,
        file_type=ext,
        file_path=file_path,
        status="pending",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return document
