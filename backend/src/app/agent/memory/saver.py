from __future__ import annotations

import asyncio
import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.redis import AsyncRedisSaver

from app.core.redis import get_redis

logger = logging.getLogger(__name__)

async_saver: BaseCheckpointSaver | None = None
lock = asyncio.Lock()


async def get_async_checkpointer() -> BaseCheckpointSaver:
    global async_saver
    if async_saver is not None:
        return async_saver

    async with lock:
        if async_saver is not None:
            return async_saver

        try:
            async_saver = AsyncRedisSaver(redis_client=await get_redis())
            await async_saver.asetup()
            logger.info("AsyncRedisSaver 就绪")
        except Exception as e:
            async_saver = MemorySaver()
            logger.warning("AsyncRedisSaver 不可用，降级为 MemorySaver: %s", e)

    return async_saver
