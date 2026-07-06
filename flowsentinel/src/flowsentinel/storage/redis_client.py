import logging
from typing import Optional, Union, Callable, Awaitable
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.client: Optional[aioredis.Redis] = None

    async def connect(self) -> None:
        if not self.client:
            self.client = aioredis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            logger.info("Connected to Redis at %s", self.redis_url)

    async def close(self) -> None:
        if self.client:
            try:
                await self.client.aclose()
            except Exception:
                pass
            logger.info("Closed Redis connection")
            self.client = None

    async def get(self, key: str) -> Optional[str]:
        if not self.client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> None:
        if not self.client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        await self.client.set(key, value, ex=ttl_seconds)

    async def is_duplicate(self, tx_hash: str, ttl_seconds: int = 60) -> bool:
        """
        Deduplicates transaction hashes. If hash is new, stores it with TTL and returns False.
        If hash was already seen within the TTL window, returns True.
        """
        if not self.client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        key = f"tx_seen:{tx_hash}"
        # setnx returns 1 if key was set, 0 if it already existed
        is_new = await self.client.set(key, "1", ex=ttl_seconds, nx=True)
        return not is_new

    async def publish(self, channel: str, message: str) -> None:
        if not self.client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        await self.client.publish(channel, message)

    async def subscribe(self, channel: str, callback: Callable[[str], Awaitable[None]]) -> None:
        if not self.client:
            raise RuntimeError("Redis client not connected. Call connect() first.")
        pubsub = self.client.pubsub()
        await pubsub.subscribe(channel)
        
        async for message in pubsub.listen():
            if message["type"] == "message":
                await callback(str(message["data"]))
