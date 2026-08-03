from functools import lru_cache

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import get_settings


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


@lru_cache
def _pool_holder() -> dict:
    return {"pool": None}


async def get_arq_pool() -> ArqRedis:
    holder = _pool_holder()
    if holder["pool"] is None:
        holder["pool"] = await create_pool(redis_settings())
    return holder["pool"]


async def close_arq_pool() -> None:
    holder = _pool_holder()
    pool = holder.get("pool")
    if pool is not None:
        await pool.close()
        holder["pool"] = None
