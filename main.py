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

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


# Create tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield
    finally:
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
async def redirect_to_original_url(short_code: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(models.URL).where(
            models.URL.short_code == short_code, models.URL.is_active
        )
    )
    url = result.scalars().first()

    if url:
        return RedirectResponse(url.original_url)
    else:
        raise HTTPException(
            status_code=404, detail=f"URL {BASE_URL}/{short_code} doesn't exist"
        )


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
