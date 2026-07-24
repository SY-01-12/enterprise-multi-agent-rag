import asyncio
from fastapi import FastAPI
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

import app.models
from app.db.session import init_db
from app.api.auth import router as auth_router
from app.api.knowledge_base import router as kb_router
from app.api.document import router as doc_router
from app.api.chat import router as chat_router
from app.api.retrieval import router as retrieval_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 后台初始化数据库，不阻塞启动
    async def init():
        try:
            await init_db()
            print("[OK] Database tables initialized successfully")
        except Exception as e:
            print(f"[WARN] Database connection failed: {e}")
    asyncio.create_task(init())
    yield


app = FastAPI(
    title="Enterprise RAG System",
    description="基于企业知识库的rag系统",
    version="0.1.0",
    lifespan=lifespan,
)

#跨域问题
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#路由注册
app.include_router(auth_router)
app.include_router(kb_router)
app.include_router(doc_router)
app.include_router(chat_router)
app.include_router(retrieval_router)

#默认测试接口
@app.get("/")
async def root():
    return {"message": "Hello World"}




