from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from app.const import OBJECTS_DIR, TMP_DIR
from app.database import engine, get_db, Base
from app.logging_config import setup_logging
from app.routers import buckets, objects
from app import models
from loguru import logger


def ensure_directories():
    os.makedirs(OBJECTS_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):

    setup_logging()

    logger.info("Initializing storage directories...")
    ensure_directories()

    logger.info("Initializing database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    logger.info("Shutting down Hako...")
    await engine.dispose()


app = FastAPI(title="Hako - Object Storage", lifespan=lifespan)


app.include_router(buckets.router)
app.include_router(objects.router)


@app.get("/health")
async def health_check():

    return {"status": "ok", "message": "Hako is running smoothly!"}
