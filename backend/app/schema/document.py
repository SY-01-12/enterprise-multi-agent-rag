from datetime import datetime
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    status: str
    created_at: datetime


class ProcessResponse(BaseModel):
    document_id: int
    chunks: int
    vectors: int
    es_indexed: int
