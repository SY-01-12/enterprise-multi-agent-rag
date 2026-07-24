from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    #Mysql  配置
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DB: str
    MYSQL_ROOT_PASSWORD: str

    # Redis 配置
    REDIS_HOST: str
    REDIS_PORT: int

    #Ollama 配置
    OLLAMA_HOST: str
    OLLAMA_PORT: int
    OLLAMA_MODEL: str

    #阿里百炼 配置
    API_KEY: str
    BASE_URL: str
    BASE_MODEL: str
    BASE_EMBEDDING_MODEL: str

    #Elasticsearch 配置
    ELASTICSEARCH_HOST: str
    ELASTICSEARCH_PORT: int

    #Chroma 配置
    CHROMA_HOST: str
    CHROMA_PORT: int

    #Embedding 模型配置
    EMBEDDING_MODEL_NAME: str

    #JWT 配置
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_TIME: int


    @property
    def DATABASE_URL(self):
        return f"mysql+aiomysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8"
    }


@lru_cache
def get_settings():
    return Settings()



