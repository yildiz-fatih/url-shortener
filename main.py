import os
from contextlib import asynccontextmanager
import secrets
import string
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import validators
from models import Base
from database import engine, get_db
import models

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


async def generate_unique_code(db, length) -> str:
    # Define allowed characters
    chars = string.ascii_uppercase + string.digits
    # Keep trying until a unique code is found
    while True:
        # Build the candidate string
        candidate = ""
        for _ in range(length):
            random_char = secrets.choice(chars)
            candidate += random_char
        # Check if this code already exists
        result = await db.execute(
            select(models.URL).where(models.URL.short_code == candidate)
        )
        # If no existing code exists, return candidate
        if not result.scalars().first():
            return candidate


@app.post("/api/urls", response_model=URLResponse, status_code=status.HTTP_201_CREATED)
async def shorten_a_url(payload: URLCreate, db: AsyncSession = Depends(get_db)):
    if not validators.url(payload.url_to_shorten):
        raise HTTPException(status_code=400, detail="Invalid URL")

    short_code = await generate_unique_code(db, 5)

    url = models.URL(original_url=payload.url_to_shorten, short_code=short_code)
    db.add(url)
    await db.commit()
    await db.refresh(url)

    return URLResponse(
        original_url=url.original_url,
        shortened_url=f"{BASE_URL}/{url.short_code}",
        is_active=url.is_active,
    )
