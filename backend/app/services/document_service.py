import os
import tempfile
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.models.documents import Document
from app.services.kb_service import get_knowledge_base_by_id
from app.langchain_app.loaders.pdf_loader import load_pdf
from app.langchain_app.loaders.docx_loader import load_docx
from app.langchain_app.loaders.txt_loader import load_txt

# 允许的文件类型
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
# 文件大小限制：50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

# 上传目录
UPLOAD_DIR = "data/uploads"


async def upload_document(
    file: UploadFile,
    knowledge_base_id: int,
    current_user: User,
    db: AsyncSession,
):
    # 1. 检查知识库是否存在
    kb = await get_knowledge_base_by_id(knowledge_base_id, db)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")

    # 2. 检查知识库权限
    if kb.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该知识库")

    # 3. 检查文件是否为空
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件不能为空")

    # 4. 检查文件格式
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: .{ext}，仅支持: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # 5. 检查文件大小
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件过大，最大支持 50MB")
    await file.seek(0)  # 重置文件指针

    # 6. 保存文件到磁盘
    kb_dir = os.path.join(UPLOAD_DIR, f"kb_{knowledge_base_id}")
    os.makedirs(kb_dir, exist_ok=True)
    file_path = os.path.join(kb_dir, file.filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # 7. 创建数据库记录
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


# 各格式对应的 Loader
LOADER_MAP = {
    "pdf": load_pdf,
    "docx": load_docx,
    "txt": load_txt,
}


async def parse_document(file: UploadFile) -> dict:
    # 1. 检查文件是否为空
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件不能为空")

    # 2. 检查格式
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    loader = LOADER_MAP.get(ext)
    if not loader:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: .{ext}，仅支持: {', '.join(LOADER_MAP.keys())}",
        )

    # 3. 临时保存文件
    suffix = f".{ext}"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # 4. 用对应 Loader 解析
        documents = loader(tmp_path)

        # 5. 统计
        total_chars = sum(len(doc.page_content) for doc in documents)
        pages = len(documents)

        return {
            "filename": file.filename,
            "pages": pages,
            "characters": total_chars,
        }
    finally:
        # 6. 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
