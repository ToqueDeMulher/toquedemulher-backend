from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from app.core.settings import settings
from app.models.product import Product


SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")
UPLOAD_CHUNK_SIZE = 1024 * 1024


@dataclass
class SupabaseSettings:
    url: str
    key: str
    bucket: str
    folder: str
    timeout: float
    max_upload_bytes: int


def get_supabase_settings() -> SupabaseSettings:
    url = settings.SUPABASE_URL
    key = settings.SUPABASE_SERVICE_ROLE_KEY
    bucket = settings.SUPABASE_BUCKET
    folder = settings.SUPABASE_FOLDER
    timeout = settings.SUPABASE_TIMEOUT
    max_upload_bytes = settings.PRODUCT_IMAGE_MAX_BYTES

    if not url or not key:
        raise HTTPException(
            status_code=500,
            detail="Supabase nao configurado. Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY.",
        )

    return SupabaseSettings(
        url=url,
        key=key,
        bucket=bucket,
        folder=folder,
        timeout=timeout,
        max_upload_bytes=max_upload_bytes,
    )


async def upload_to_supabase(*, product_id: UUID, file: UploadFile, extension: str) -> str:
    supabase_settings = get_supabase_settings()

    file_key = f"{supabase_settings.folder}/{product_id}/{uuid4().hex}{extension}"
    upload_url = f"{supabase_settings.url}/storage/v1/object/{supabase_settings.bucket}/{file_key}"

    file_bytes = await read_upload_bytes(file=file, max_bytes=supabase_settings.max_upload_bytes)

    headers = {
        "Authorization": f"Bearer {supabase_settings.key}",
        "apikey": supabase_settings.key,
        "Content-Type": file.content_type or "application/octet-stream",
        "x-upsert": "true",
    }

    async with httpx.AsyncClient(timeout=supabase_settings.timeout) as client:
        response = await client.post(upload_url, headers=headers, content=file_bytes)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=500,
            detail=f"Supabase retornou erro {response.status_code}: {response.text}",
        )

    return f"{supabase_settings.url}/storage/v1/object/public/{supabase_settings.bucket}/{file_key}"


async def read_upload_bytes(*, file: UploadFile, max_bytes: int) -> bytes:
    await file.seek(0)

    total_size = 0
    chunks: list[bytes] = []

    while True:
        chunk = await file.read(UPLOAD_CHUNK_SIZE)
        if not chunk:
            break

        total_size += len(chunk)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Arquivo excede o limite de {max_bytes} bytes.",
            )

        chunks.append(chunk)

    return b"".join(chunks)


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = SLUG_INVALID_CHARS.sub("-", ascii_value.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or uuid4().hex[:8]


def generate_unique_slug(session: Session, name: str) -> str:
    base_slug = slugify(name)
    slug = base_slug
    counter = 1
    while session.exec(select(Product).where(Product.slug == slug)).first():
        counter += 1
        slug = f"{base_slug}-{counter}"
    return slug
