# Enterprise Multi-Agent RAG Assistant

企业级智能知识库助手。基于 LangGraph + FastAPI + Vue3，集成知识库检索、图片生成、数学计算、跨会话记忆等一站式企业 AI 能力。

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (Vue3)                      │
│                  Nginx :80 → API :8000                   │
└────────────────────────┬────────────────────────────────┘
                         │ /api/*
                         ▼
┌─────────────────────────────────────────────────────────┐
│                Backend (FastAPI + LangGraph)              │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              LangGraph Agent                       │   │
│  │  ┌─────────┐ ┌──────────┐ ┌────────────┐        │   │
│  │  │RAG检索   │ │图片生成   │ │MCP工具      │        │   │
│  │  │知识库    │ │wanx-v1   │ │计算/地图    │        │   │
│  │  └─────────┘ └──────────┘ └────────────┘        │   │
│  │  ┌──────────────────────────────────────────┐    │   │
│  │  │     SummarizationMiddleware               │    │   │
│  │  │     30轮触发摘要，保留20轮短期记忆          │    │   │
│  │  └──────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────┐ ┌──────┐ ┌──────────┐ ┌───────────────┐   │
│  │Hybrid   │ │Rerank │ │Embedding │ │Document       │   │
│  │Retrieval│ │BGE    │ │DashScope │ │Loader Pipeline│   │
│  │RRF Fusion│ │       │ │          │ │               │   │
│  └─────────┘ └──────┘ └──────────┘ └───────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────────────┐
│ MySQL 8  │  │  Redis   │  │ Elasticsearch 8  │
│ 业务数据  │  │ 记忆/缓存 │  │    全文检索       │
└──────────┘  └──────────┘  └──────────────────┘
                         │
                         ▼
               ┌──────────────────┐
               │    ChromaDB       │
               │    向量数据库      │
               └──────────────────┘
```

## 检索流程

```
用户问题
  │
  ▼
Embedding 向量化 (DashScope text-embedding)
  │
  ├──→ ChromaDB 语义检索 ──┐
  │                         │
  ├──→ Elasticsearch BM25 ──┤
  │                         │
  └─────────────────────────┘
              │
              ▼
        RRF 融合排序
              │
              ▼
        BGE CrossEncoder 重排序
              │
              ▼
        Top-K 结果 → LLM 生成回答
```

## 项目结构

```
├── docker-compose.yml         # 一键部署全部服务
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt       # Python 依赖
│   ├── .env_example           # 环境变量模板
│   ├── mcp_servers/           # MCP 服务
│   │   └── calculator_server.py
│   └── src/app/
│       ├── main.py            # FastAPI 入口
│       ├── agent/             # LangGraph Agent
│       │   ├── factory.py     # Agent 工厂
│       │   ├── prompt.py      # 提示词
│       │   ├── state.py       # 状态定义
│       │   ├── tools/         # 工具集 (RAG/图片/时间/记忆)
│       │   ├── memory/        # 记忆系统 (Redis Checkpoint+Store)
│       │   └── mcp/           # MCP 客户端
│       ├── api/               # API 路由 (auth/chat/document/kb)
│       ├── rag/               # RAG 引擎
│       │   ├── retriever/     # Chroma / ES / Hybrid / Reranker
│       │   ├── loader/        # 文档加载器 (PDF/DOCX/XLSX/TXT/IMG)
│       │   └── splitter/      # 文本分割器
│       ├── services/          # 业务逻辑层
│       ├── models/            # SQLAlchemy 数据模型
│       ├── schema/            # Pydantic Schema
│       ├── llm/               # LLM 适配 (百炼/Ollama/Vision)
│       ├── embedding/         # Embedding 适配
│       ├── core/              # 配置/异常/日志/安全
│       └── db/                # 数据库会话
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
│       ├── views/             # Chat / Knowledge / Login / Register
│       ├── components/        # ChatMessage
│       ├── api/               # Axios 请求封装
│       ├── router/            # Vue Router
│       └── stores/            # Pinia 用户状态
└── tests/                     # 测试用例

## 界面截图

### 对话页面

![chat](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/2e4b0a6e-6bb2-4dcc-a3df-42a418fbf4af.png)

![kb-qa](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/bfd1946c-e7b9-49a6-94ab-eca8346a8a26.png)

![stream](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/e890073a-61ca-4648-b163-1325c5160286.png)

![image](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/29fcbcd0-3289-48f4-a13a-3149a11af8c8.png)

![multi](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/20033cac-4072-41ac-ba5d-082474f648b5.png)

![memory](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/3d22a922-3fe2-4f28-aae4-003cf972cdd0.png)

### 知识库管理

![kb-list](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/d4fcbad8-04f3-415a-8707-65cd3d440570.png)

![docs](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/98d30ce5-0021-4465-b062-779fd5147070.png)

### AI 生成图片

![gen1](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/10408e9d-c057-414c-8b7f-df871585f2af.png)

![gen2](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/c8d6f803-e6c7-448d-a40f-35b24c413e1a.png)

![gen3](https://raw.githubusercontent.com/SY-01-12/enterprise-multi-agent-rag/main/pic/dff9f68b-85c6-4b49-8c56-552a43771f76.png)

## 核心能力

| 能力 | 工具 | 实现 |
|------|------|------|
| 知识库检索 | search_knowledge_base | 混合检索(RRF融合) + BGE CrossEncoder 重排序 |
| 图片生成 | generate_image | DashScope wanx-v1 文生图 |
| 数学计算 | calculator | MCP Server 安全表达式求值 |
| 时间查询 | current_time | 实时日期时间获取 |
| 跨会话记忆 | remember/recall/forget | Redis Stack Store 持久化 |
| 地图服务 | amap_maps_* | 高德 MCP 集成 (路线/搜索/天气) |
| 文件问答 | /api/file/ask | 上传文件直接问答 |

## 快速启动

### 前置条件

- Docker & Docker Compose
- 阿里百炼 API Key

### 1. 配置

```bash
cp backend/.env_example backend/.env
# 编辑 backend/.env，填入 API_KEY
```

### 2. 启动

```bash
docker-compose up -d
```

服务端口：

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| API 文档 | http://localhost:8000/docs |
| RedisInsight | http://localhost:8002 |

### 3. 本地开发

```bash
# 启动基础设施
docker-compose up -d mysql redis chromadb elasticsearch

# 后端
cd backend && pip install -r requirements.txt
PYTHONPATH=src uvicorn app.main:app --reload --port 8000

# 前端
cd frontend && npm install && npm run dev
```

## 配置参考

| 变量 | 说明 | 默认值 |
|------|------|--------|
| API_KEY | 阿里百炼 API Key | 必填 |
| BASE_URL | LLM API 地址 | dashscope 兼容 |
| BASE_MODEL | 默认模型 | qwen-turbo |
| BASE_EMBEDDING_MODEL | Embedding 模型 | text-embedding-v3 |
| RERANKER_MODEL | 重排序模型 | BAAI/bge-reranker-base |
| MYSQL_HOST/PORT/DB | MySQL 连接 | 127.0.0.1:3307 |
| REDIS_HOST/PORT | Redis 连接 | 127.0.0.1:6379 |
| ELASTICSEARCH_HOST/PORT | ES 连接 | 127.0.0.1:9200 |
| CHROMA_HOST/PORT | ChromaDB 连接 | 127.0.0.1:8001 |
| JWT_SECRET_KEY | JWT 签名密钥 | 必填 |

## 技术栈

| 层 | 技术 |
|------|------|
| Agent | LangGraph + langgraph-supervisor |
| LLM | 阿里百炼 DashScope (qwen-turbo/plus/max) |
| Embedding | DashScope text-embedding |
| Web | FastAPI + SSE 流式 |
| 向量库 | ChromaDB |
| 全文检索 | Elasticsearch 8 |
| 数据库 | MySQL 8 |
| 记忆/缓存 | Redis Stack |
| 重排序 | BGE CrossEncoder (bge-reranker-base) |
| 前端 | Vue 3 + Element Plus + Vite |
| 部署 | Docker Compose + Nginx |

## License

MIT
