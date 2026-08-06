from datetime import datetime
from pydantic import BaseModel, Field

# 新增知识库所需信息
class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: str = Field(..., min_length=1, max_length=500, description="知识库描述")

# 前端显示知识库信息
class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    owner_name: str = ""
    created_at: datetime
