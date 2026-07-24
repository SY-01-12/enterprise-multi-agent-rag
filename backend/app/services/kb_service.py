from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import User
from app.models.knowleged_bases import KnowledgeBase
from app.schema.knowledge_base import KnowledgeBaseCreate


class KbAlreadyExistsError(Exception):
    pass


async def get_knowledge_by_name(kb_name: str, db: AsyncSession):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.name == kb_name))
    return result.scalars().one_or_none()


async def get_knowledge_base_by_id(kb_id: int, db: AsyncSession):
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    return result.scalars().one_or_none()


async def get_knowledge_bases_by_owner(owner_id: int, db: AsyncSession):
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.owner_id == owner_id)
    )
    return result.scalars().all()


async def create_knowledge_base(
    db: AsyncSession,
    current_user: User,
    knowledge_data: KnowledgeBaseCreate,
):
    # 检查同名知识库
    existing = await get_knowledge_by_name(knowledge_data.name, db)
    if existing and existing.owner_id == current_user.id:
        raise KbAlreadyExistsError("知识库名称已存在")

    kb = KnowledgeBase(
        name=knowledge_data.name,
        description=knowledge_data.description,
        owner_id=current_user.id,
    )
    db.add(kb)
    await db.commit()
    await db.refresh(kb)
    return kb


async def delete_knowledge_base(kb: KnowledgeBase, db: AsyncSession):
    await db.delete(kb)
    await db.commit()
