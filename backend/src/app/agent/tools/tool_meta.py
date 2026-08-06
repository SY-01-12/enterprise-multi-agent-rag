from __future__ import annotations

from langchain_core.tools import BaseTool

tool_registry: dict[str, str] = {}


def register_tools(tools: list[BaseTool]) -> None:
    """MCP 工具加载后调用，缓存 name → description。"""
    for t in tools:
        tool_registry[t.name] = t.description or ""


def get_desc(tool_name: str) -> str:
    """获取工具描述，不存在返回空字符串。"""
    return tool_registry.get(tool_name, "")
