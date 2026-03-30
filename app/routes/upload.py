# app/routes/upload.py
import asyncio
import os
import uuid
from urllib.parse import urlsplit

import requests
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/upload", tags=["Upload"])

# All images are stored on Hostinger — no local disk writes.
HOSTINGER_UPLOAD_URL      = os.getenv("HOSTINGER_UPLOAD_URL", "").strip()
HOSTINGER_UPLOAD_TOKEN    = os.getenv("HOSTINGER_UPLOAD_TOKEN", "").strip()
HOSTINGER_UPLOAD_FIELD    = (os.getenv("HOSTINGER_UPLOAD_FIELD", "image") or "image").strip()
HOSTINGER_PUBLIC_BASE_URL = os.getenv("HOSTINGER_PUBLIC_BASE_URL", "").strip()
HOSTINGER_UPLOAD_TIMEOUT  = int(os.getenv("HOSTINGER_UPLOAD_TIMEOUT", "60"))

# Allowed image mime types
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

# Max file size: 10 MB
MAX_SIZE_BYTES = 10 * 1024 * 1024


def _to_absolute_hostinger_url(remote_url: str) -> str:
    """Convert whatever upload.php returns into a guaranteed absolute public URL."""
    value = (remote_url or "").strip()
    if not value:
        return value
    if value.startswith("http://") or value.startswith("https://"):
        return value
    if HOSTINGER_PUBLIC_BASE_URL:
        return f"{HOSTINGER_PUBLIC_BASE_URL.rstrip('/')}/{value.lstrip('/')}"
    if HOSTINGER_UPLOAD_URL:
        parsed = urlsplit(HOSTINGER_UPLOAD_URL)
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}/{value.lstrip('/')}"
    return value


def _forward_to_hostinger(filename: str, content_type: str, contents: bytes) -> dict:
    headers = {}
    if HOSTINGER_UPLOAD_TOKEN:
        headers["Authorization"] = f"Bearer {HOSTINGER_UPLOAD_TOKEN}"

    files = {
        HOSTINGER_UPLOAD_FIELD: (
            filename,
            contents,
            content_type or "application/octet-stream",
        )
    }

    response = requests.post(
        HOSTINGER_UPLOAD_URL,
        headers=headers,
        files=files,
        timeout=HOSTINGER_UPLOAD_TIMEOUT,
    )
    response.raise_for_status()

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Hostinger upload.php returned a non-JSON response.",
        ) from exc

    absolute_url = _to_absolute_hostinger_url(data.get("url", ""))
    if not absolute_url:
        raise HTTPException(
            status_code=502,
            detail="Hostinger upload response missing 'url' field.",
        )

    return {
        "url": absolute_url,
        "filename": data.get("filename") or filename,
        "storage": "hostinger",
    }


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    # Hostinger must be configured — no local fallback.
    if not HOSTINGER_UPLOAD_URL:
        raise HTTPException(
            status_code=503,
            detail=(
                "Image storage is not configured. "
                "Set HOSTINGER_UPLOAD_URL in the Railway environment variables."
            ),
        )

    # ── Validate mime type ───────────────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file.content_type}'. Only JPEG, PNG, WEBP allowed.",
        )

    # ── Read file and check size ─────────────────────────────────────────────
    contents = await file.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10 MB.",
        )

    # ── Generate a unique filename preserving extension ──────────────────────
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"

    # ── Upload to Hostinger (always) ─────────────────────────────────────────
    try:
        payload = await asyncio.to_thread(
            _forward_to_hostinger,
            filename,
            file.content_type,
            contents,
        )
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Hostinger upload failed: {exc}",
        ) from exc

    return JSONResponse(payload)
