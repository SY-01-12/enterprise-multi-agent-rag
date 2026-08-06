import asyncio
import sys
from pathlib import Path

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

import app.models
from app.db.session import init_db
from app.core.redis import get_redis, close_redis
from app.core.exceptions import AppException
from app.core.exception_handlers import app_exception_handler, generic_exception_handler
from app.core.logging import setup_logging, get_logger
from app.api.auth import router as auth_router
from app.api.knowledge_base import router as kb_router
from app.api.document import router as doc_router
from app.api.chat import router as chat_router
from app.api.retrieval import router as retrieval_router
from app.api.file_chat import router as file_chat_router
from app.rag.retriever.reranker import get_reranker
from app.embedding.dashscope import get_embedding_model

logger = get_logger(__name__)

_CALC_SERVER = str(Path(__file__).resolve().parent.parent.parent / "mcp_servers" / "calculator_server.py")


def warmup_models():
    get_reranker()
    get_embedding_model()


@asynccontextmanager
async def lifespan(app: FastAPI):
    calc_proc = None
    try:
        calc_proc = await asyncio.create_subprocess_exec(
            sys.executable, _CALC_SERVER,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        logger.info("Calculator MCP server started (pid=%d)", calc_proc.pid)
    except Exception as e:
        logger.warning("Calculator MCP server failed to start: %s", e)

    async def init():
        try:
            await init_db()
        except Exception as e:
            logger.warning("Database connection failed: %s", e)
        try:
            await get_redis()
        except Exception as e:
            logger.warning("Redis connection failed: %s", e)
        try:
            await asyncio.to_thread(warmup_models)
        except Exception as e:
            logger.warning("ML model preload skipped: %s", e)

    asyncio.create_task(init())
    yield
    if calc_proc:
        calc_proc.terminate()
        await calc_proc.wait()
        logger.info("Calculator MCP server stopped")
    await close_redis()


app = FastAPI(
    title="Enterprise RAG System",
    description="基于企业知识库的AI助手",
    version="0.1.0",
    lifespan=lifespan,
)

# ── 日志系统初始化 ──
setup_logging()

# GZip 压缩 — 大于 500 字节的响应自动压缩，减少传输体积
app.add_middleware(GZipMiddleware, minimum_size=500)

# 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局异常处理
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

#路由注册
app.include_router(auth_router)
app.include_router(kb_router)
app.include_router(doc_router)
app.include_router(chat_router)
app.include_router(retrieval_router)
app.include_router(file_chat_router)
# 健康检查
@app.get("/api/health")
async def health():
    return {"status": "ok"}

# 默认测试接口
@app.get("/")
async def root():
    return {"message": "Enterprise RAG System", "version": "0.1.0"}




