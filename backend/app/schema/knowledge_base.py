from datetime import datetime
from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="知识库名称")
    description: str = Field(..., min_length=1, max_length=500, description="知识库描述")


class KnowledgeBaseResponse(BaseModel):
    id: int
    name: str
    description: str
    owner_id: int
    created_at: datetime
