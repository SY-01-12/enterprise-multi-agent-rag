from typing import Any

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig


def _resolve(config: RunnableConfig) -> tuple[Any, tuple[str, str]]:
    cfg = config.get("configurable", {})
    return cfg.get("store"), ("memories", str(cfg.get("user_id", "default")))


@tool
def remember(key: str, value: str, config: RunnableConfig) -> str:
    """记住用户的个人信息、偏好、习惯。用户分享值得记住的内容时调用。"""
    store, ns = _resolve(config)
    if store is None:
        return "记忆服务暂不可用，但我已经记在心里了。"
    store.put(ns, key, {"value": value})
    return f"已记住: {key} = {value}"


@tool
def recall(key: str, config: RunnableConfig) -> str:
    """查询用户之前说过的信息。key 为空时列出全部记忆。"""
    store, ns = _resolve(config)
    if store is None:
        return "暂无任何跨会话记忆。"
    if key:
        item = store.get(ns, key)
        if item and item.value:
            return f"{key}: {item.value.get('value', '无记录')}"
        return f"未找到关于「{key}」的记忆。"
    items = store.search(ns)
    if not items:
        return "暂无任何跨会话记忆。"
    return "已记住的信息：\n" + "\n".join(
        f"- {it.key}: {it.value.get('value', '')}" for it in items
    )


@tool
def forget(key: str, config: RunnableConfig) -> str:
    """删除某条已记住的信息。"""
    store, ns = _resolve(config)
    if store is None:
        return "记忆服务暂不可用。"
    store.delete(ns, key)
    return f"已删除记忆: {key}"
