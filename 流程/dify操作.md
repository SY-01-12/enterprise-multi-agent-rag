# Dify 编排操作指南：从 0 到 1

> 将现有 LangChain Enterprise RAG 项目迁移到 [Dify](https://dify.ai) 平台进行可视化编排。

---

## 一、项目现状速览

| 组件 | 当前方案 | Dify 对应方案 |
|---|---|---|
| LLM | 阿里百炼（ChatOpenAI 兼容） | 百炼模型接入 / OpenAI 兼容 |
| Embedding | DashScopeEmbeddings | 百炼 Embedding 接入 |
| 单 Agent | `langchain.agents.create_agent` | ReAct Agent 节点 |
| 多 Agent | `langgraph_supervisor.create_supervisor` | 多 Agent 编排 / 条件分支 |
| 知识库 | Chroma + ES + Reranker | Dify 知识库（内置） |
| 短期记忆 | Redis Checkpointer | Dify 对话变量 + 上下文窗口 |
| 长期记忆 | RedisStore | Dify 变量持久化 / 外部存储 |
| MCP 工具 | 自定义 MCP Registry | Dify 工具插件 / API 工具 |
| 文档处理 | fitz + LangChain Loader | Dify 知识库上传（自动处理） |

---

## 二、环境准备

### 2.1 安装 Dify

```bash
# 方式一：Docker Compose（推荐）
git clone https://github.com/langgenius/dify.git
cd dify/docker
cp .env.example .env
# 编辑 .env，设置 SECRET_KEY
docker compose up -d

# 方式二：Dify Cloud
# 直接访问 https://cloud.dify.ai 注册使用
```

### 2.2 启动后访问

```
http://localhost:3000   # Dify 控制台
http://localhost:5001   # API 服务
```

---

## 三、模型提供商配置

### 3.1 阿里百炼（LLM + Embedding）

1. 进入 **设置 → 模型供应商**
2. 添加 **阿里云百炼**（或 OpenAI-API-compatible）
3. 填入配置：

```
API Key:      <你的百炼 API_KEY>
Base URL:     https://dashscope.aliyuncs.com/compatible-mode/v1

系统推理模型:  qwen-max (或 qwen-plus)
Embedding:     text-embedding-v2 (对应 settings.BASE_EMBEDDING_MODEL)
多模态模型:    qwen-vl-max (用于 OCR / 图片理解)
```

### 3.2 Ollama（可选本地模型）

1. 进入 **设置 → 模型供应商 → Ollama**
2. 填入 Ollama 服务地址：`http://127.0.0.1:11434`
3. 点击"获取模型列表"，选择对应模型

---

## 四、知识库搭建

> 替代：`rag/loader/*` + `rag/splitter/*` + `Chroma/ES` + `reranker`

### 4.1 创建知识库

1. **知识库 → 创建知识库**
2. 配置：

| 参数 | 建议值 | 对应代码 |
|---|---|---|
| 名称 | 企业知识库 | — |
| 索引方式 | 高质量 | — |
| Embedding 模型 | text-embedding-v2 | `DashScopeEmbeddings` |
| 检索方式 | 混合检索 | `hybrid_search()`（Chroma + ES） |
| 重排序 | BAAI/bge-reranker-base | `reranker.py` → `get_reranker()` |
| 分段最大长度 | 1000 | `chunk_size=1000` |
| 分段重叠长度 | 200 | `chunk_overlap=200` |
| 分段规则 | 自动分段与清洗 | `RecursiveCharacterTextSplitter` |

### 4.2 上传文档

1. **知识库 → 文档 → 上传文件**
2. 支持格式：PDF、Word、Excel、TXT、图片（Dify 内置图片 OCR）
3. 上传后自动：**加载 → 清洗 → 分块 → Embedding → 索引**

> ⚠️ Dify 知识库已内置分块和检索，原有 `hybrid_search()` + `reranker.py` 逻辑无需迁移。

### 4.3 扫描件 PDF 处理

Dify 平台版自带 OCR，无需额外配置（对应 `ocr.py` → `ocr_image()`）。

---

## 五、单 Agent 编排（知识库问答）

> 替代：`create_agent(kb_id, role="rag")` + `RAG_AGENT_PROMPT`

### 5.1 创建 Chatflow

1. **工作室 → 创建应用 → Chatflow**
2. 拖入以下节点：

```
┌──────────┐    ┌─────────────────┐    ┌──────────────┐    ┌──────────┐
│  开始节点  │───→│   知识检索节点     │───→│   LLM 节点    │───→│  直接回复  │
└──────────┘    │ (知识库问答 Agent) │    │ (RAG Prompt)  │    └──────────┘
                └─────────────────┘    └──────────────┘
```

### 5.2 知识检索节点配置

```
查询变量:         {{#sys.query#}}
知识库:           企业知识库
检索模式:          混合检索
召回条数 (Top K):  5
分数阈值:          0.5
重排序:            开启 (BAAI/bge-reranker-base)
```

### 5.3 LLM 节点配置（System Prompt）

使用原项目的 `RAG_AGENT_PROMPT`：

```text
你是企业知识库智能助手，专门用于检索和回答企业文档相关问题。

你的能力：
- 通过知识库检索工具查找文档内容
- 执行数学计算
- 获取当前日期时间

规则：
1. 涉及企业知识库内容的问题，必须先检索知识库再回答
2. 不确定的问题诚实告知
3. 用中文简洁回答

上下文：
{{#context#}}
```

---

## 六、多 Agent 编排（Supervisor 模式）

> 替代：`create_supervisor(rag, general)` + `SUPERVISOR_SYSTEM_PROMPT`

### 6.1 架构设计

```
                     ┌───────────────┐
                     │   Supervisor   │
                     │  (LLM 路由节点) │
                     └───┬───────┬───┘
                    ↙              ↘
          ┌──────────────┐   ┌──────────────┐
          │  RAG Agent   │   │ General Agent │
          │  (知识库检索)  │   │  (通用工具)    │
          └──────────────┘   └──────────────┘
                    ↘              ↙
                     ┌──────────┐
                     │  回复节点  │
                     └──────────┘
```

### 6.2 实现方式一：条件分支（推荐，简单场景）

在 Chatflow 中添加 **条件分支** 节点：

```
开始 → 知识检索 → 条件分支 → RAG 分支 → LLM → 回复
                           → General 分支 → 工具调用 → LLM → 回复
```

条件判断：
```python
# 根据问题类型路由
if 包含["文档","制度","流程","规范","手册"]:
    → RAG 分支
else:
    → General 分支
```

### 6.3 实现方式二：Multi-Agent（复杂场景，Dify 2.0+）

1. 创建两个独立的 Chatflow 应用：
   - **RAG Agent**：知识库 + 计算器 + 时间工具
   - **General Agent**：图片生成 + 写作 + 翻译 + 计算 + 地图 + 天气

2. 创建 **Supervisor** Chatflow，通过 **Agent 节点** 调用子 Agent：

```
开始
  │
  ▼
LLM 路由分析（SUPERVISOR_SYSTEM_PROMPT）
  │
  ├─→ Agent 节点[rag_agent]  ──→ 回复
  ├─→ Agent 节点[general_agent] ──→ 回复
  └─→ 直接回复（问候/确认）
```

---

## 七、工具（Tools）接入

> 替代：`agent/tools/*` + `agent/mcp/registry.py`

### 7.1 内置工具

Dify 已内置以下工具，直接使用：

| 工具 | 原项目 | Dify |
|---|---|---|
| 计算器 | `tools/datetime.py` | 内置计算器工具 |
| 当前时间 | `tools/datetime.py` | 内置时间工具 |
| 图片生成 | `tools/image_gen.py` | 内置图片生成 |
| 记忆 | `tools/memory.py` | Dify 变量持久化 |

### 7.2 外部 API 工具

对应原项目的 MCP 工具（高德地图、天气）：

1. **工具 → 创建自定义工具 → OpenAPI/Swagger**
2. 导入 API Schema 或手动配置：

```yaml
# 高德地图搜索
名称: 高德地图搜索
方法: GET
URL: https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp/search
认证: Bearer Token
Header: Authorization: Bearer <API_KEY>
```

### 7.3 代码工具

对应 `calculator_server.py`（MCP Calculator）：

```python
# 工具 → 代码工具 → 新建
def main(expression: str) -> float:
    """执行数学计算"""
    import math
    import re
    # 安全过滤
    safe = re.sub(r'[^0-9+\-*/.()%\s]', '', expression)
    return eval(safe)
```

---

## 八、记忆系统配置

> 替代：Redis Checkpointer + RedisStore

### 8.1 短期记忆（对话上下文）

```
Chatflow 设置 → 对话变量：
├── conversation_history: array[object]  (最近 10 轮)
└── session_summary: string             (历史摘要)
```

**上下文窗口**：设置 → 对话设置 → 上下文窗口大小 = 10 轮

### 8.2 长期记忆（跨会话）

使用 Dify **变量** 功能：

```
工作流变量（持久化）:
├── user_preferences: object    (用户偏好，如 {language: "zh", style: "简洁"})
└── user_facts: array[string]  (remember/recall/forget 功能)
```

代码工具：

```python
# remember 工具
def remember(key: str, value: str, user_id: str) -> str:
    import json
    import os
    path = f"/data/memory/{user_id}.json"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path) as f:
            mem = json.load(f)
    except:
        mem = {}
    mem[key] = value
    with open(path, 'w') as f:
        json.dump(mem, f)
    return f"已记住: {key}"
```

---

## 九、API 发布与前端对接

### 9.1 发布应用

1. 应用 → **发布**
2. 获取 API 密钥：**API 访问 → 创建密钥**

### 9.2 前端对接

修改 `frontend/src` 中的 API 地址：

```javascript
// 原: POST /api/chat/stream  → 自己的 FastAPI
// 改: POST https://api.dify.ai/v1/chat-messages  → Dify API

const response = await fetch('https://api.dify.ai/v1/chat-messages', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer <DIFY_API_KEY>',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    inputs: { knowledge_base_id: 1 },
    query: question,
    response_mode: 'streaming',
    conversation_id: sessionId,  // Dify 对话 ID（替代 thread_id）
    user: currentUser.id,
  }),
});
```

### 9.3 API 路由对照

| 原 FastAPI 路由 | Dify API |
|---|---|
| `POST /api/chat/stream` | `POST /v1/chat-messages` (streaming) |
| `GET /api/chat/history/{id}` | `GET /v1/messages?conversation_id={id}` |
| `GET /api/chat/sessions` | `GET /v1/conversations?user={user_id}` |
| `DELETE /api/chat/sessions/{id}` | `DELETE /v1/conversations/{id}` |
| `POST /api/knowledge_base/upload` | Dify 知识库 → `POST /v1/datasets/{id}/documents` |
| `POST /api/document/process` | Dify 自动处理，无需手动触发 |

---

## 十、环境变量对照

| 原 `.env` 变量 | Dify 对应位置 |
|---|---|
| `API_KEY` | 模型供应商 → 百炼 → API Key |
| `BASE_URL` | 模型供应商 → 百炼 → Base URL |
| `BASE_MODEL` | 应用设置 → 系统推理模型 |
| `BASE_EMBEDDING_MODEL` | 知识库设置 → Embedding 模型 |
| `OCR_MODEL` | 模型供应商 → 百炼 → 多模态模型 |
| `CHROMA_HOST/PORT` | Dify 内置，无需配置 |
| `ELASTICSEARCH_HOST/PORT` | Dify 内置，无需配置 |
| `REDIS_HOST/PORT` | Dify 内置 |
| `MYSQL_*` | Dify 内置（PostgreSQL） |
| `JWT_*` | Dify 内置认证 |

---

## 十一、迁移检查清单

- [ ] 安装 Dify（Docker Compose）
- [ ] 配置百炼模型供应商
- [ ] 创建知识库 + 上传文档（批量）
- [ ] 创建 **RAG Agent** Chatflow（知识库 → LLM → 回复）
- [ ] 创建 **General Agent** Chatflow（工具调用 → LLM → 回复）
- [ ] 创建 **Supervisor** Chatflow（路由子 Agent）
- [ ] 配置工具：计算器、时间、图片生成、高德地图、天气
- [ ] 配置记忆：对话变量 + 长期记忆工具
- [ ] 发布应用 + 获取 API 密钥
- [ ] 修改前端 API 地址
- [ ] 端到端测试：知识库问答 / 通用问答 / 多轮对话 / 自动路由
- [ ] 关闭原 FastAPI 服务

---

## 十二、注意事项

1. **扫描件 PDF**：Dify 平台版自带 OCR 处理，但需要确保已购买对应模型额度。
2. **百炼 API**：Dify 的 OpenAI-API-compatible 模式完全兼容百炼，`BASE_URL` 填 `https://dashscope.aliyuncs.com/compatible-mode/v1`。
3. **知识库迁移**：已有 Chroma/ES 数据需要重新上传到 Dify 知识库，Dify 不支持直接迁移外部向量数据库。
4. **MCP 工具**：Dify 当前不原生支持 MCP 协议，需将 MCP Server 转换为 API 工具或代码工具。
5. **成本**：Dify Cloud 按 token 计费，自部署（Docker Compose）零额外平台费用，仅消耗百炼 API 费用。
6. **数据安全**：自部署 Dify 确保企业数据不离开服务器。
