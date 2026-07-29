"""Cloudflare R2 (S3-compatible) object storage helper.

R2 is S3-compatible, so we use boto3 pointed at the R2 endpoint. boto3 is imported
lazily so the API still boots if it isn't installed (e.g. before `pip install`).

Until R2 is configured (R2_* env vars), `public_url()` falls back to a local
"/images/..." path so the dev dashboard keeps working off the local images/ dir.
"""
from __future__ import annotations

import logging
import mimetypes
from functools import lru_cache
from pathlib import Path

from api.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _client():
    """Return a cached boto3 S3 client configured for R2, or None if unavailable."""
    if not settings.r2_enabled:
        return None
    try:
        import boto3  # lazy
    except ImportError:
        logger.warning("boto3 not installed — R2 disabled (pip install boto3)")
        return None
    endpoint = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def public_url(key: str) -> str:
    """Public URL for an object key, or a local /images fallback in dev."""
    if settings.R2_PUBLIC_BASE_URL:
        return f"{settings.R2_PUBLIC_BASE_URL.rstrip('/')}/{key.lstrip('/')}"
    return f"/images/{key.lstrip('/')}"


def upload_file(local_path: str | Path, key: str, *, content_type: str | None = None) -> bool:
    """Upload a local file to R2 under `key`. Returns True on success."""
    client = _client()
    if client is None:
        logger.info("[r2 dry-run] would upload %s -> %s", local_path, key)
        return False
    ctype = content_type or mimetypes.guess_type(str(local_path))[0] or "application/octet-stream"
    try:
        client.upload_file(
            str(local_path),
            settings.R2_BUCKET,
            key,
            ExtraArgs={"ContentType": ctype},
        )
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("R2 upload failed (%s): %s", key, exc)
        return False


def object_exists(key: str) -> bool:
    client = _client()
    if client is None:
        return False
    try:
        client.head_object(Bucket=settings.R2_BUCKET, Key=key)
        return True
    except Exception:  # noqa: BLE001
        return False
