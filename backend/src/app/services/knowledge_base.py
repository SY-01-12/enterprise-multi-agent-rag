from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException

from app.core.exceptions import KnowledgeBaseAlreadyExists
from app.models import User
from app.models.knowleged_bases import KnowledgeBase
from app.schema.knowledge_base import KnowledgeBaseCreate
from app.models.users import User as UserModel

# 查询

async def get_knowledge_by_name(kb_name: str, db: AsyncSession):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.name == kb_name))
    return result.scalars().one_or_none()


async def get_knowledge_base_by_id(kb_id: int, db: AsyncSession):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    return result.scalars().one_or_none()


async def get_knowledge_bases_by_owner(owner_id: int, db: AsyncSession) -> list[KnowledgeBase]:

    # 根据 owner_id（用户ID）去数据库里查出这个人拥有的所有知识库记录
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.owner_id == owner_id),
    )
    kbs = list(result.scalars().all())

    # 填充 owner_name
    # 先收集所有知识库的 owner_id
    owner_ids = {kb.owner_id for kb in kbs}
    if owner_ids:
        # 拿这些 ID 去用户表里批量查出对应的 用户名
        user_result = await db.execute(
            select(UserModel.id, UserModel.username).where(UserModel.id.in_(owner_ids)),
        )
        # 把查到的用户名填回到每个知识库对象的 owner_name 字段上
        id_to_name = {row[0]: row[1] for row in user_result.all()}
        for kb in kbs:
            kb.owner_name = id_to_name.get(kb.owner_id, f"用户#{kb.owner_id}")
    return kbs


async def get_all_knowledge_bases(db: AsyncSession) -> list[KnowledgeBase]:
    """返回所有知识库（含 owner_name），供已登录用户浏览和问答。"""
    result = await db.execute(select(KnowledgeBase).order_by(KnowledgeBase.created_at.desc()))
    kbs = list(result.scalars().all())
    owner_ids = {kb.owner_id for kb in kbs}
    if owner_ids:
        user_result = await db.execute(
            select(UserModel.id, UserModel.username).where(UserModel.id.in_(owner_ids)),
        )
        id_to_name = {row[0]: row[1] for row in user_result.all()}
        for kb in kbs:
            kb.owner_name = id_to_name.get(kb.owner_id, f"用户#{kb.owner_id}")
    return kbs


# 权限检查
async def require_owner(kb_id: int, user_id: int, db: AsyncSession) -> KnowledgeBase:

    kb = await get_knowledge_base_by_id(kb_id, db)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.owner_id != user_id:
        raise HTTPException(status_code=403, detail="无权操作该知识库")
    return kb

# 创建知识库
async def create_knowledge_base(
    db: AsyncSession,
    current_user: User,
    knowledge_data: KnowledgeBaseCreate,
):
    existing = await get_knowledge_by_name(knowledge_data.name, db)
    if existing and existing.owner_id == current_user.id:
        raise KnowledgeBaseAlreadyExists("知识库名称已存在")

    kb = KnowledgeBase(
        name=knowledge_data.name,
        description=knowledge_data.description,
        owner_id=current_user.id,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb

# 删除数据库
async def delete_knowledge_base(kb: KnowledgeBase, db: AsyncSession):
    await db.delete(kb)
    await db.commit()
