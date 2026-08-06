from __future__ import annotations

import logging

from langchain_core.documents import Document as LangchainDocument

from app.rag.retriever.chroma import get_langchain_chroma
from app.rag.retriever.elasticsearch import search_content

logger = logging.getLogger(__name__)

RRF_K = 60


def rrf_fuse(
    chroma_ranked: list[tuple[LangchainDocument, int]],
    es_ranked: list[tuple[LangchainDocument, int]],
    top_n: int,
) -> list[LangchainDocument]:
    # "文档内容字符串" → (累计得分, 文档对象)
    fused: dict[str, tuple[float, LangchainDocument]] = {}
    for source in (chroma_ranked, es_ranked):
        for doc, rank in source:
            # 用 page_content 当 key 做去重——两个系统都命中了同一篇文档时，分数要累加。
            key = doc.page_content
            score = 1.0 / (RRF_K + rank)
            prev = fused.get(key)
            fused[key] = (prev[0] + score if prev else score, doc)
            #fused.values()： [(0.032, DocA), (0.016, DocB), (0.015, DocC)]
            #sorted(..., key=lambda x: x[0],reverse=True)      → 按得分从高到低排
            #最终至返回 Document 对象， score 分数去掉
    return [doc for _, doc in sorted(fused.values(), key=lambda x: x[0], reverse=True)[:top_n]]


def hybrid_search(
    kb_id: int,
    query: str,
    top_k: int = 5,
) -> list[LangchainDocument]:
    fetch_k = top_k * 3

    # 1. chroma 向量检索
    # 获取 chroma 向量库
    vectorstore = get_langchain_chroma(kb_id)
    # chroma 检索
    chroma_results = vectorstore.similarity_search_with_score(query, k=fetch_k)
    # chroma 检索排序 (doc,_) 去掉原始的 向量距离分数，只需要Document(page_content,metadata) 排名按 索引+1 处理
    chroma_ranked = [(doc, rank + 1) for rank, (doc, _) in enumerate(chroma_results)]

    #2. es 全文检索
    es_ranked: list[tuple[LangchainDocument, int]] = []
    try:
        for rank, r in enumerate(search_content(query, size=fetch_k)):
            # 去掉 es的BM25打分 分数
            es_ranked.append((
                LangchainDocument(page_content=r["content"],
                                  metadata={"source": r.get("source", "ES 全文检索")}),
                rank + 1,
            ))
    except Exception:
        logger.warning("ES 检索失败，跳过关键词召回 (kb_id=%d, query=%.50s)", kb_id, query)

    # 3. RRF 融合
    candidates = rrf_fuse(chroma_ranked, es_ranked, top_n=top_k * 2)
    if not candidates:
        return []

    # 4. CrossEncoder 重排序
    from app.rag.retriever.reranker import rerank
    contents = [d.page_content for d in candidates]
    ranked = rerank(query, contents, top_k=top_k)
    # 用索引捞出最终文档
    return [candidates[idx] for idx, _ in ranked]
