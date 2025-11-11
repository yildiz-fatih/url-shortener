import os
import redis.asyncio as redis
from fastapi import FastAPI, Request

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")


# Initializes the Redis client and stores it in app.state
async def init_redis(app: FastAPI):
    app.state.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)


async def close_redis(app: FastAPI):
    if hasattr(app.state, "redis"):
        await app.state.redis.aclose()


# Provides the Redis client from the app state
async def get_redis(request: Request) -> redis.Redis:
    return request.app.state.redis
