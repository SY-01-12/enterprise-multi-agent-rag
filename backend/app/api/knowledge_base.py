from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.schema.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseResponse
from app.services.kb_service import (
    KbAlreadyExistsError,
    create_knowledge_base,
    get_knowledge_base_by_id,
    get_knowledge_bases_by_owner,
    delete_knowledge_base,
)

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
    try:
        kb = await create_knowledge_base(db, current_user, knowledge_data)
    except KbAlreadyExistsError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return kb

# 查询当前用户所有知识库
@router.get("/list", response_model=list[KnowledgeBaseResponse], summary="查询所有知识库")
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_knowledge_bases_by_owner(current_user.id, db)

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
    if kb.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")
    return kb


# 删除知识库
@router.delete("/delete/{id}", summary="删除知识库")
async def delete(
    id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    kb = await get_knowledge_base_by_id(id, db)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")

    await delete_knowledge_base(kb, db)
    return {"message": "删除成功"}


@router.get("/{kb_id}/documents", summary="知识库文档列表")
async def list_documents(
    kb_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取指定知识库中的所有文档（含状态：pending/processed/failed）。"""
    from sqlalchemy import select
    from app.models.documents import Document

    kb = await get_knowledge_base_by_id(kb_id, db)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问")

    result = await db.execute(
        select(Document)
        .where(Document.knowledge_base_id == kb_id)
        .order_by(Document.created_at.desc())
    )
    docs = result.scalars().all()
    return [
        {
            "id": d.id,
            "filename": d.filename,
            "file_type": d.file_type,
            "status": d.status,
            "created_at": d.created_at.isoformat(),
        }
        for d in docs
    ]
