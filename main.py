import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import validators
from models import Base
from database import engine, get_db
import models
from utils import encode_id
from cache import init_redis, close_redis, get_redis
import redis.asyncio as redis

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))  # Default 5 min


# Manage startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Startup: Initialize Redis
    await init_redis(app)

    try:
        yield
    finally:
        # Shutdown: Close Redis
        await close_redis(app)
        # Shutdown: Dispose of the database engine
        await engine.dispose()


app = FastAPI(lifespan=lifespan)


# Data transfer objects
class URLCreate(BaseModel):
    url_to_shorten: str


class URLResponse(BaseModel):
    original_url: str
    shortened_url: str
    is_active: bool


@app.get("/{short_code}")
async def redirect_to_original_url(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    # Cache lookup
    try:
        cached_url = await redis_client.get(short_code)
        if cached_url:
            return RedirectResponse(cached_url)
    except Exception as e:
        print(f"Cache lookup failed for {short_code}: {e}")

    result = await db.execute(
        select(models.URL).where(
            models.URL.short_code == short_code, models.URL.is_active
        )
    )
    url = result.scalars().first()
    if not url:
        raise HTTPException(
            status_code=404, detail=f"URL {BASE_URL}/{short_code} doesn't exist"
        )

    # Set cache for future requests
    try:
        await redis_client.set(short_code, url.original_url, ex=CACHE_TTL_SECONDS)
    except Exception as e:
        print(f"Failed to cache {short_code}: {e}")

    return RedirectResponse(url.original_url)


@app.post("/api/urls", response_model=URLResponse, status_code=status.HTTP_201_CREATED)
async def shorten_a_url(payload: URLCreate, db: AsyncSession = Depends(get_db)):
    if not validators.url(payload.url_to_shorten):
        raise HTTPException(status_code=400, detail="Invalid URL")

    url = models.URL(original_url=payload.url_to_shorten)
    db.add(url)
    await db.flush()

    short_code = encode_id(url.id)
    url.short_code = short_code
    await db.commit()
    await db.refresh(url)

    return URLResponse(
        original_url=url.original_url,
        shortened_url=f"{BASE_URL}/{url.short_code}",
        is_active=url.is_active,
    )


@app.delete("/api/urls/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_url(
    short_code: str,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
):
    result = await db.execute(
        select(models.URL).where(
            models.URL.short_code == short_code, models.URL.is_active
        )
    )
    url = result.scalars().first()
    if not url:
        raise HTTPException(
            status_code=404, detail=f"URL {BASE_URL}/{short_code} doesn't exist"
        )

    # Update database first
    url.is_active = False
    await db.commit()

    # Best effort cache invalidation (TTL ensures eventual consistency if this fails)
    try:
        await redis_client.delete(short_code)
    except Exception as e:
        print(f"Failed to remove cache for {short_code}: {e}")
