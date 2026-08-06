from __future__ import annotations

import redis.asyncio as aioredis
import redis as sync_redis

from app.core.config import get_settings

async_client: aioredis.Redis | None = None
sync_client: sync_redis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global async_client
    if async_client is None:
        settings = get_settings()
        async_client = aioredis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
    return async_client


def get_sync_redis() -> sync_redis.Redis:
    global sync_client
    if sync_client is None:
        settings = get_settings()
        sync_client = sync_redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=False,
        )
    return sync_client


async def close_redis() -> None:
    global async_client
    if async_client is not None:
        await async_client.aclose()
        async_client = None


#缓存 Key 约定
def token_blacklist_key(token_jti: str) -> str:
    return f"token:blacklist:{token_jti}"
