
from __future__ import annotations

import logging

from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore
from langgraph.store.redis import RedisStore

from app.core.redis import get_sync_redis

logger = logging.getLogger(__name__)

store_instance: BaseStore | None = None


def get_store() -> BaseStore:
    global store_instance
    if store_instance is not None:
        return store_instance

    client = get_sync_redis()
    try:
        store_instance = RedisStore(conn=client)
        store_instance.put(("__health__",), "__ok__", {"v": 1})
        store_instance.delete(("__health__",), "__ok__")
        logger.info("RedisStore 就绪（跨会话长期记忆）")
    except Exception as e:
        store_instance = InMemoryStore()
        logger.warning(
            "RedisStore 不可用（需 Redis Stack），降级为 InMemoryStore。"
            "原因: %s", e
        )

    return store_instance
