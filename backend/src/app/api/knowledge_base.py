from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.schema.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.schema.document import DocumentResponse
from app.services.knowledge_base import (
    create_knowledge_base,
    get_knowledge_base_by_id,
    get_knowledge_bases_by_owner,
    get_all_knowledge_bases,
    delete_knowledge_base,
    require_owner,
)
from app.models.documents import Document

router = APIRouter(
    prefix="/api/knowledge-base",
    tags=["知识库"],
)

# 创建知识库
@router.post("/create", response_model=KnowledgeBaseResponse, summary="创建知识库")
async def create(
    knowledge_data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_knowledge_base(db, current_user, knowledge_data)

# 知识库列表（所有已登录用户可见全部知识库）
@router.get("/list", response_model=list[KnowledgeBaseResponse], summary="知识库列表")
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_all_knowledge_bases(db)

# 知识库详情
@router.get("/detail/{id}", response_model=KnowledgeBaseResponse, summary="知识库详情")
async def detail(
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kb = await get_knowledge_base_by_id(id, db)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    # 填充 owner_name
    from app.models.users import User as UserModel
    result = await db.execute(select(UserModel.username).where(UserModel.id == kb.owner_id))
    row = result.one_or_none()
    kb.owner_name = row[0] if row else f"用户#{kb.owner_id}"
    return kb

# 删除知识库
@router.delete("/delete/{id}", summary="删除知识库（仅 owner）")
async def delete(
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kb = await require_owner(id, current_user.id, db)
    await delete_knowledge_base(kb, db)
    return {"message": "删除成功"}

# 文档列表（仅 owner 可查看）
@router.get("/{kb_id}/documents", response_model=list[DocumentResponse], summary="知识库文档列表")
async def list_documents(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kb = await get_knowledge_base_by_id(kb_id, db)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看文档列表")
    result = await db.execute(
        select(Document)
        .where(Document.knowledge_base_id == kb_id)
        .order_by(Document.created_at.desc())
    )
    return result.scalars().all()
