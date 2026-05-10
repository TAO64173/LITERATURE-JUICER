"""
可选 Redis 缓存层
未配置 REDIS_URL 时自动降级为无缓存模式
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

_redis_client = None
_cache_enabled = False

# 配置
CACHE_TTL = 120  # 秒
NEGATIVE_CACHE_TTL = 300  # 无效卡密缓存更久


def init_cache():
    """初始化 Redis 连接（如可用）"""
    global _redis_client, _cache_enabled

    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        logger.info("[cache] REDIS_URL 未配置，缓存禁用")
        return

    try:
        import redis
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        _redis_client.ping()
        _cache_enabled = True
        logger.info("[cache] Redis 连接成功，缓存已启用")
    except Exception as e:
        logger.warning(f"[cache] Redis 连接失败，缓存禁用: {e}")
        _redis_client = None
        _cache_enabled = False


def get_cached_quota(code: str) -> int | None:
    """从缓存获取卡密剩余配额，返回 None 表示未命中"""
    if not _cache_enabled:
        return None

    try:
        key = f"card:{code}"
        val = _redis_client.get(key)
        if val is None:
            return None
        data = json.loads(val)
        return data.get("remaining")
    except Exception as e:
        logger.warning(f"[cache] 读取失败: {e}")
        return None


def set_cached_quota(code: str, remaining: int) -> None:
    """写入缓存"""
    if not _cache_enabled:
        return

    try:
        key = f"card:{code}"
        ttl = NEGATIVE_CACHE_TTL if remaining <= 0 else CACHE_TTL
        _redis_client.setex(key, ttl, json.dumps({"remaining": remaining}))
    except Exception as e:
        logger.warning(f"[cache] 写入失败: {e}")


def invalidate_code(code: str) -> None:
    """使缓存失效（扣费后调用）"""
    if not _cache_enabled:
        return

    try:
        _redis_client.delete(f"card:{code}")
    except Exception as e:
        logger.warning(f"[cache] 删除失败: {e}")


def is_cache_enabled() -> bool:
    return _cache_enabled
