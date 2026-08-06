from __future__ import annotations
import logging
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.sessions import SSEConnection, StreamableHttpConnection
from app.core.config import get_settings


# 日志文件
logger = logging.getLogger(__name__)

# MCP 服务器配置
SERVERS = {
    "calculator": SSEConnection(transport="sse", url="http://127.0.0.1:8765/sse"),
    "amap": StreamableHttpConnection(
        transport="streamable_http",
        url="https://dashscope.aliyuncs.com/api/v1/mcps/amap-maps/mcp",
        headers={"Authorization": f"Bearer {get_settings().API_KEY}"},
    ),
}

mcp_cache: list[BaseTool] | None = None

# MCP 工具加载
async def get_mcp_tools() -> list[BaseTool]:
    global mcp_cache
    if mcp_cache is not None:
        return mcp_cache

    try:
        client = MultiServerMCPClient(connections=SERVERS, tool_name_prefix=True)
        mcp_cache = await client.get_tools()
        from app.agent.tools.tool_meta import register_tools
        register_tools(mcp_cache)
        logger.info("MCP 加载完成: %s", [t.name for t in mcp_cache])

    except Exception as e:
        logger.warning("MCP 连接失败: %s", e)
        mcp_cache = []

    return mcp_cache
