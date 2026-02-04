import redis
from app.core.config import get_settings

settings = get_settings()

try:
    redis_client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        decode_responses=True
    )
except Exception as e:
    print(f"Redis connection failed: {e}")
    redis_client = None

def get_redis_client():
    return redis_client
