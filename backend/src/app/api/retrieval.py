from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import get_current_user
from app.db.session import get_db
from app.models import User
from app.schema.retrieval import RetrievalRequest, RetrievalResult, RetrievalResponse
from app.rag.retriever.hybrid import hybrid_search

router = APIRouter(
    prefix="/api/retrieval",
    tags=["检索"],
)

# 知识库检索
@router.post("/search", response_model=RetrievalResponse, summary="知识库检索")
async def search(
    request: RetrievalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):

# 执行混合检索
    docs = hybrid_search(
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
