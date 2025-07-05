import os
import redis
import logging
import json

REDIS_EXPIRE_SECONDS = 48 * 3600  # 48 hours

redis_client = None

# Prefer REDIS_URL if set (works for Upstash and most cloud Redis)
REDIS_URL = os.getenv("REDIS_URL")
REDIS_MODE = os.getenv("REDIS_MODE", "auto")  # "auto", "upstash", or "local"

try:
    if REDIS_URL:
        redis_client = redis.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            ssl=REDIS_URL.startswith("rediss://")
        )
        redis_client.ping()
        print(f"✅ Connected to Redis at {REDIS_URL}")
    elif REDIS_MODE == "upstash":
        # Legacy Upstash envs
        REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL")
        REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
        if not REDIS_URL or not REDIS_TOKEN:
            raise ValueError("REDIS_URL and REDIS_TOKEN must be set for Upstash mode")
        redis_client = redis.Redis.from_url(
            REDIS_URL,
            password=REDIS_TOKEN,
            decode_responses=True,
            ssl=True
        )
        redis_client.ping()
        print(f"✅ Connected to Upstash Redis at {REDIS_URL}")
    else:
        REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
        REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
        REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', None)
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True
        )
        redis_client.ping()
        print(f"✅ Connected to local Redis at {REDIS_HOST}:{REDIS_PORT}")
except Exception as e:
    redis_client = None
    print(f"❌ Failed to connect to Redis: {e}")
    logging.error(f"Failed to connect to Redis: {e}")

def redis_set_user_roles(user_id, role_ids):
    if not redis_client:
        logging.warning("Redis unavailable, cannot set user roles.")
        return
    try:
        key = f"user_roles:{user_id}"
        redis_client.set(key, json.dumps(role_ids), ex=REDIS_EXPIRE_SECONDS)
    except Exception as e:
        logging.error(f"Redis set error for user {user_id}: {e}")

def redis_get_user_roles(user_id):
    if not redis_client:
        logging.warning("Redis unavailable, cannot get user roles.")
        return None
    try:
        key = f"user_roles:{user_id}"
        data = redis_client.get(key)
        if isinstance(data, bytes):
            data = data.decode()
        if not isinstance(data, str):
            return None
        if data:
            return json.loads(data)
        return None
    except Exception as e:
        logging.error(f"Redis get error for user {user_id}: {e}")
        return None

def redis_delete_user_roles(user_id):
    if not redis_client:
        return
    try:
        key = f"user_roles:{user_id}"
        redis_client.delete(key)
    except Exception as e:
        logging.error(f"Redis delete error for user {user_id}: {e}") 