import hashlib
import mimetypes
import os
import select
import uuid
import aiofiles
from fastapi import APIRouter, Depends, Request, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from loguru import logger

from app.const import OBJECTS_DIR, TMP_DIR
from app.database import get_db
from app.models import Bucket, Key, Object
from app.schemas import ObjectResponse


router = APIRouter(prefix="/objects", tags=["Objects"])


@router.put("/{bucket}/{key:path}")
async def upload_object(
    bucket: str, key: str, request: Request, db: AsyncSession = Depends(get_db)
):
    # print(f"Starting upload for bucket: {bucket}, key: {key}")

    result = await db.execute(select(Bucket).where(Bucket.name == bucket))

    if not result.scalar_one_or_none():
        # print(f" Failed : Bucket {bucket} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found"
        )

    temp_filename = f"{uuid.uuid4().hex}.part"
    temp_filepath = os.path.join(TMP_DIR, temp_filename)

    sha256_hash = hashlib.sha256()
    file_size = 0

    try:
        async with aiofiles.open(temp_filepath, "wb") as f:
            async for chunk in request.stream():
                await f.write(chunk)
                sha256_hash.update(chunk)
                file_size += len(chunk)
        final_hash = sha256_hash.hexdigest()
        # print(f"Upload streamed. Size: {file_size} bytes, Hash: {final_hash}")

        prefix = final_hash[:2]
        target_dir = os.path.join(OBJECTS_DIR, prefix)
        os.makedirs(target_dir, exist_ok=True)

        final_filepath = os.path.join(target_dir, final_hash)

        os.replace(temp_filepath, final_filepath)

        statement_obj = (
            sqlite_insert(Object)
            .values(hash=final_hash, size=file_size)
            .on_conflict_do_nothing(index_elements=["hash"])
        )

        await db.execute(statement_obj)

        statement_key = (
            sqlite_insert(Key)
            .values(bucket=bucket, key=key, hash=final_hash)
            .on_conflict_do_update(
                index_elements=["bucket", "key"], set_=dict(hash=final_hash)
            )
        )

        await db.execute(statement_key)

        await db.commit()
        # print(
        #     f"Upload completed successfully for bucket: {bucket}, key: {key}, hash: {final_hash}"
        # )

        return {"message": "Upload successful", "hash": final_hash, "size": file_size}
    except Exception as e:
        # print(f"Upload failed : {e}")

        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Upload failed"
        )


@router.get("/{bucket}/{key:path}")
async def download_object(
    bucket: str, key: str, request: Request, db: AsyncSession = Depends(get_db)
):

    logger.info(f"Download request for '{bucket}/{key}")

    statement = select(Key).where(Key.bucket == bucket, Key.key == key)
    result = await db.execute(statement)
    key_record = result.scalar_one_or_none()

    if not key_record:
        logger.warning(f"Key '{key}' not found in bucket '{bucket}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object not found"
        )

    object_hash = key_record.hash
    prefix = object_hash[:2]
    file_path = os.path.join(OBJECTS_DIR, prefix, object_hash)

    if not os.path.exists(file_path):
        logger.warning(f"Object '{key}' not found in bucket '{bucket}'")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object not found"
        )

    file_size = os.path.getsize(file_path)
    content_type, _ = mimetypes.guess_type(key)
    content_type = content_type or "application/octet-stream"

    range_header = request.headers.get("range")
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Type": content_type,
    }

    if range_header:
        logger.debug(f"Range request detected: {range_header}")

        try:
            byte_range = range_header.replace("bytes=", "").split("-")
            start = int(byte_range[0]) if byte_range[0] else 0
            end = (
                int(byte_range[1])
                if len(byte_range) > 1 and byte_range[1]
                else file_size - 1
            )

            if start >= file_size or end >= file_size or start > end:
                raise ValueError("Invalid range values")

        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                detail="Invalid Range header",
            )

        chunk_size = end - start + 1
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
        headers["Content-Length"] = str(chunk_size)
        status_code = status.HTTP_206_PARTIAL_CONTENT

    else:
        start = 0
        end = file_size - 1
        chunk_size = file_size
        headers["Content-Length"] = str(file_size)
        status_code = status.HTTP_200_OK

    async def file_iterator(path: str, start_byte: int, total_bytes_to_read: int):
        CHUNK_SIZE = 1024 * 1024
        bytes_read = 0

        async with aiofiles.open(path, "rb") as f:
            await f.seek(start_byte)
            while bytes_read < total_bytes_to_read:
                read_size = min(CHUNK_SIZE, total_bytes_to_read - bytes_read)
                chunk = await f.read(read_size)

                if not chunk:
                    break
                bytes_read += len(chunk)

                yield chunk

    logger.debug(f"Starting {chunk_size} bytes (Status: {status_code})'")

    return StreamingResponse(
        file_iterator(file_path, start, chunk_size),
        status_code=status_code,
        headers=headers,
    )


@router.get("/{bucket}/objects", response_model=list[ObjectResponse])
async def list_objects(bucket: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"Listing objects in bucket: {bucket}")

    bucket_check = await db.execute(select(Bucket).where(Bucket.name == bucket))
    if not bucket_check.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bucket not found"
        )

    statement = (
        select(Key.key, Object.size, Object.created_at)
        .join(Object, Key.hash == Object.hash)
        .where(Key.bucket == bucket)
    )
    result = await db.execute(statement)

    objects = [
        {"key": row.key, "size": row.size, "created_at": row.created_at.isoformat()}
        for row in result
    ]
    return objects


@router.delete("/{bucket}/{key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_object(bucket: str, key: str, db: AsyncSession = Depends(get_db)):
    logger.info(f"Attempting to delete object '{key}' from bucket '{bucket}'")

    statement = select(Key).where(Key.bucket == bucket, Key.key == key)
    result = await db.execute(statement)
    key_record = result.scalar_one_or_none()

    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Object not found"
        )

    target_hash = key_record.hash

    await db.delete(key_record)
    await db.flush()

    ref_statement = select(Key).where(Key.hash == target_hash).limit(1)
    ref_result = await db.execute(ref_statement)
    remaining_reference = ref_result.scalar_one_or_none()

    if not remaining_reference:
        logger.info(f"No more references to object with hash '{target_hash}'. Deleting file.")

        obj_statement = select(Object).where(Object.hash == target_hash)
        obj_result = await db.execute(obj_statement)
        obj_record = obj_result.scalar_one_or_none()

        if obj_record:
            await db.delete(obj_record)

        prefix = target_hash[:2]
        file_path = os.path.join(OBJECTS_DIR, prefix, target_hash)

        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"File '{file_path}' deleted successfully.")

            prefix_dir = os.path.dirname(file_path)
            if not os.listdir(prefix_dir):
                os.rmdir(prefix_dir)
                logger.info(f"Prefix directory '{prefix_dir}' removed as it is now empty.")
        else:
            logger.warning(f"File '{file_path}' not found.")

    else:
        logger.info(
            f"Object with hash '{target_hash}' still has references. Skipping file deletion."
        )

    await db.commit()
    logger.info(f"Object '{key}' deleted successfully from bucket '{bucket}'")
    return None
