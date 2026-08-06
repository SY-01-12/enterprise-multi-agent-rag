from datetime import datetime
from pydantic import BaseModel

# 前端显示文档信息
class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    status: str
    created_at: datetime

# 处理文档信息
class ProcessResponse(BaseModel):
    document_id: int
    chunks: int
    vectors: int
    es_indexed: int
