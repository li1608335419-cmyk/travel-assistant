import fakeredis
import pytest

from data.redis_memory import RedisMemoryStore


@pytest.fixture
def memory_store():
    client = fakeredis.FakeRedis(decode_responses=True)
    return RedisMemoryStore(client=client, ttl_seconds=600, max_history=4)
