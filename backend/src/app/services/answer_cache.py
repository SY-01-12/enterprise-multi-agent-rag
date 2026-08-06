import hashlib
import logging
import re

from app.core.config import get_settings
from app.core.redis import get_sync_redis

logger = logging.getLogger(__name__)


def _norm(q: str) -> str:
    return re.sub(r"[！-～]", lambda m: chr(ord(m.group()) - 0xFEE0), re.sub(r"\s+", " ", q).strip())[:200]


def _key(kb_id: int, question: str) -> str:
    return f"cache:answer:{kb_id}:{hashlib.md5(_norm(question).encode()).hexdigest()}"  # noqa: S324


def get_cached_answer(kb_id: int, question: str) -> str | None:
    try:
        key = _key(kb_id, question)
        if cached := get_sync_redis().get(key):
            logger.info("答案缓存命中: kb=%d", kb_id)
            return cached.decode("utf-8")
    except Exception:
        logger.warning("答案缓存查询失败", exc_info=True)
    return None


def set_cached_answer(kb_id: int, question: str, answer: str, ttl: int | None = None) -> None:
    if len(answer.strip()) < 10:
        return
    try:
        key = _key(kb_id, question)
        get_sync_redis().setex(key, ttl or get_settings().ANSWER_CACHE_TTL, answer)
        logger.info("答案已缓存: kb=%d, ttl=%ds", kb_id, ttl or get_settings().ANSWER_CACHE_TTL)
    except Exception:
        logger.warning("答案缓存写入失败", exc_info=True)
