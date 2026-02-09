from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, UploadFile
from sqlmodel import Session, select

from ignore import Ignore
from app.features.products.models import Product


SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")


@dataclass
class SupabaseSettings:
    url: str
    key: str
    bucket: str
    folder: str
    timeout: float


def get_supabase_settings() -> SupabaseSettings:
    url = Ignore.SUPABASE_URL
    key = Ignore.SUPABASE_SERVICE_ROLE_KEY
    bucket = Ignore.SUPABASE_BUCKET
    folder = Ignore.SUPABASE_FOLDER
    timeout = float(Ignore.SUPABASE_TIMEOUT)

    if not url or not key:
        raise HTTPException(
            status_code=500,
            detail="Supabase nao configurado. Defina SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY.",
        )

    return SupabaseSettings(url=url, key=key, bucket=bucket, folder=folder, timeout=timeout)


async def upload_to_supabase(*, product_id: UUID, file: UploadFile, extension: str) -> str:
    settings = get_supabase_settings()

    file_key = f"{settings.folder}/{product_id}/{uuid4().hex}{extension}"
    upload_url = f"{settings.url}/storage/v1/object/{settings.bucket}/{file_key}"

    await file.seek(0)
    file_bytes = await file.read()

    headers = {
        "Authorization": f"Bearer {settings.key}",
        "apikey": settings.key,
        "Content-Type": file.content_type or "application/octet-stream",
        "x-upsert": "true",
    }

    async with httpx.AsyncClient(timeout=settings.timeout) as client:
        response = await client.post(upload_url, headers=headers, content=file_bytes)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=500,
            detail=f"Supabase retornou erro {response.status_code}: {response.text}",
        )

    return f"{settings.url}/storage/v1/object/public/{settings.bucket}/{file_key}"


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
