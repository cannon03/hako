import re
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from loguru import logger

from app.database import get_db
from app.models import Bucket, Key
from app.schemas import BucketResponse


router = APIRouter(prefix="/buckets", tags=["Buckets"])

BUCKET_REGEX = re.compile(r"^[a-z0-9-]{3,63}$")


@router.put(
    "/{bucket}", response_model=BucketResponse, status_code=status.HTTP_201_CREATED
)
async def create_bucket(bucket: str, db: AsyncSession = Depends(get_db)):
    if not BUCKET_REGEX.match(bucket):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bucket name. Use 3-63 lowercase letters, numbers, or hyphens.",
        )

    logger.info(f"Attempting to create bucket: {bucket}")

    new_bucket = Bucket(name=bucket)
    db.add(new_bucket)

    try:
        await db.commit()
        await db.refresh(new_bucket)
        logger.info(f"Bucket created successfully: {new_bucket.name}")
        return new_bucket

    except IntegrityError:
        await db.rollback()
        logger.warning(f"Bucket creation failed: {bucket} already exists.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Bucket already exists."
        )


@router.get("", response_model=list[BucketResponse])
async def list_buckets(db: AsyncSession = Depends(get_db)):
    logger.info("Listing all buckets")
    result = await db.execute(select(Bucket))
    buckets = result.scalars().all()
    return buckets


@router.delete("/{bucket}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bucket(bucket: str, db: AsyncSession = Depends(get_db)):

    logger.info(f"Attempting to delete bucket: {bucket}")

    result = await db.execute(select(Bucket).where(Bucket.name == bucket))
    target_bucket = result.scalar_one_or_none()

    if not target_bucket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found."
        )

    keys_result = await db.execute(select(Key).where(Key.bucket == bucket).limit(1))

    if keys_result.scalar_one_or_none():
        logger.warning(f"Failed: Cannot delete bucket '{bucket}' because it contains keys.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bucket is not empty."
        )

    await db.delete(target_bucket)
    await db.commit()
    logger.info(f"Bucket '{bucket}' deleted successfully.")
    return None
