import redis
from app.core.config import get_settings

settings = get_settings()

try:
    redis_client = redis.Redis.from_url(
        settings.resolved_redis_url,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
        retry_on_timeout=False,
    )
except Exception as e:
    print(f"Redis connection failed: {e}")
    redis_client = None

def get_redis_client():
    return redis_client
