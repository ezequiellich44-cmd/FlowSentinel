import pytest
from unittest.mock import AsyncMock
from flowsentinel.storage.redis_client import RedisClient

@pytest.mark.asyncio
async def test_redis_deduplication_mock():
    """
    Unit test for transaction hash deduplication using a mocked Redis client.
    """
    client = RedisClient("redis://localhost:6379/0")
    mock_redis = AsyncMock()
    client.client = mock_redis

    # Mock set(..., nx=True) behavior:
    # Returns True/OK (success) for new key, False/None for existing key.
    mock_redis.set.side_effect = [True, False]

    # First call: Transaction hasn't been seen, should return False (not duplicate)
    is_dup1 = await client.is_duplicate("0xhash1", ttl_seconds=30)
    assert is_dup1 is False
    mock_redis.set.assert_called_with("tx_seen:0xhash1", "1", ex=30, nx=True)

    # Second call: Transaction has been seen, should return True (is duplicate)
    is_dup2 = await client.is_duplicate("0xhash1", ttl_seconds=30)
    assert is_dup2 is True


@pytest.mark.integration
@pytest.mark.asyncio
async def test_redis_deduplication_integration():
    """
    Integration test checking deduplication logic against a running Redis container.
    """
    import os
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    client = RedisClient(redis_url)
    try:
        await client.connect()
        if client.client:
            await client.client.ping()
    except Exception as e:
        pytest.skip(f"Redis not available: {e}")
        return
        
    try:
        tx_hash = "0xintegration_test_hash"
        
        # Clean up any residual keys first
        if client.client:
            await client.client.delete(f"tx_seen:{tx_hash}")
            
        # First check (should be new)
        assert await client.is_duplicate(tx_hash, ttl_seconds=5) is False
        # Second check (should be duplicate)
        assert await client.is_duplicate(tx_hash, ttl_seconds=5) is True
        
    finally:
        await client.close()
