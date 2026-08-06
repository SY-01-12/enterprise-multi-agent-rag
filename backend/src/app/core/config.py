from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DB: str

    REDIS_HOST: str
    REDIS_PORT: int

    API_KEY: str
    BASE_URL: str
    BASE_MODEL: str
    BASE_EMBEDDING_MODEL: str

    OCR_MODEL: str = "qwen-vl-max"

    OLLAMA_HOST: str = "127.0.0.1"
    OLLAMA_PORT: int = 11434
    OLLAMA_MODEL: str = ""

    ELASTICSEARCH_HOST: str
    ELASTICSEARCH_PORT: int

    CHROMA_HOST: str
    CHROMA_PORT: int

    RERANKER_MODEL: str = "BAAI/bge-reranker-base"

    # ── 分层记忆 & 摘要模型 ──



    # ── 热点问题缓存 ──
    ANSWER_CACHE_TTL: int = 3600  # 答案缓存过期时间（秒），默认 1 小时

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_TIME: int

    LOG_LEVEL: str = "INFO"

    @property
    def DATABASE_URL(self):
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parent.parent.parent.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings():
    return Settings()
