import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.db.base import Base
from app.core.config import get_settings


settings = get_settings()

#创建数据库引擎与异步引擎
ASYNC_DATABASE_URL = f"{settings.DATABASE_URL}"

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,                    # 生产环境关闭 SQL 日志
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,            # 连接前检测可用性
    connect_args={"connect_timeout": 5},  # 5 秒连接超时，避免启动卡死
)

#创建初始化表
async def init_db():
    try:
        async with asyncio.timeout(5):  # 最多等 5 秒
            async with async_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
    except (asyncio.TimeoutError, Exception):
        pass  # 数据库不可用，静默跳过

#创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

#获取数据库会话
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except:
            await session.rollback()
            raise
        finally:
            await session.close()