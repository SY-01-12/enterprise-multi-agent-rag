from pydantic import BaseModel, Field

# 检索请求
class RetrievalRequest(BaseModel):
    knowledge_base_id: int = Field(..., description="知识库 ID")
    query: str = Field(..., min_length=1, max_length=2000, description="搜索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")

# 检索结果
class RetrievalResult(BaseModel):
    content: str = Field(..., description="文档片段内容")
    source: str = Field(..., description="来源文件名")
    score: float | None = Field(default=None, description="相似度分数（如有）")

# 检索响应
class RetrievalResponse(BaseModel):
    results: list[RetrievalResult] = Field(..., description="检索结果列表")
    total: int = Field(..., description="结果总数")
    