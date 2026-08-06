from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import get_settings

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder

# 全局单例
reranker_instance: CrossEncoder | None = None

# 获取全局唯一的 CrossEncoder 模型实例（懒加载）
def get_reranker() -> CrossEncoder:

    global reranker_instance
    if reranker_instance is None:
        # 延迟加载——Reranker 模型太重了，不等到真正要用的时候绝不动它
        from sentence_transformers import CrossEncoder  # noqa: F811
        settings = get_settings()
        reranker_instance = CrossEncoder(
            settings.RERANKER_MODEL,
            max_length=512,
        )
    return reranker_instance

# 对候选文档进行 CrossEncoder 重排序
def rerank(query: str, documents: list[str], top_k: int) -> list[tuple[int, float]]:

    if not documents:
        return []

    model = get_reranker()

    # 构建问题-文档配对  ("公司年假怎么算", "年假每年5天...")
    pairs = [(query, doc) for doc in documents]

    # 模型逐一打分  show_progress_bar=False：关掉 tqdm 进度条   # [0.91, 0.78, 0.85, 0.12]
    scores = model.predict(pairs, show_progress_bar=False)

    # 给分数贴上原始索引，按分数从高到低排序
    indexed_scores = list(enumerate(scores))    #  # [(0, 0.91), (1, 0.78), (2, 0.85), (3, 0.12)]
    indexed_scores.sort(key=lambda x: x[1], reverse=True)   #  # [(0, 0.91), (2, 0.85), (1, 0.78), (3, 0.12)]

    return indexed_scores[:top_k]
