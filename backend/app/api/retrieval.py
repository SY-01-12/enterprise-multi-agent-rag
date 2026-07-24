"""检索 API — 知识库搜索接口。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models import User
from app.services.kb_service import get_knowledge_base_by_id
from app.services.retrieval_service import retrieve, format_docs

router = APIRouter(
    prefix="/api/retrieval",
    tags=["检索"],
)


class RetrievalRequest(BaseModel):
    knowledge_base_id: int = Field(..., description="知识库 ID")
    query: str = Field(..., min_length=1, max_length=2000, description="搜索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")


class RetrievalResult(BaseModel):
    content: str = Field(..., description="文档片段内容")
    source: str = Field(..., description="来源文件名")
    score: float | None = Field(default=None, description="相似度分数（如有）")


class RetrievalResponse(BaseModel):
    results: list[RetrievalResult] = Field(..., description="检索结果列表")
    total: int = Field(..., description="结果总数")


@router.post("/search", response_model=RetrievalResponse, summary="知识库检索")
async def search(
    request: RetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """在指定知识库中搜索相关内容。

    用于调试检索效果，或供前端实现自定义展示。
    """
    # 验证知识库权限
    kb = await get_knowledge_base_by_id(request.knowledge_base_id, db)
    if not kb:
        raise HTTPException(status_code=404, detail="知识库不存在")
    if kb.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该知识库")

    # 执行检索
    docs = retrieve(
        kb_id=request.knowledge_base_id,
        query=request.query,
        top_k=request.top_k,
    )

    results = [
        RetrievalResult(
            content=doc.page_content,
            source=doc.metadata.get("source", "未知文档"),
        )
        for doc in docs
    ]

    return RetrievalResponse(results=results, total=len(results))
