# app/routes/upload.py
import asyncio
import os
import uuid
from urllib.parse import urlsplit

import aiofiles
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/upload", tags=["Upload"])

# Folder where images are saved (relative to where uvicorn is started)
UPLOAD_DIR = "static/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Optional: forward uploads to a remote server (Hostinger, etc.)
HOSTINGER_UPLOAD_URL = os.getenv("HOSTINGER_UPLOAD_URL", "").strip()
HOSTINGER_UPLOAD_TOKEN = os.getenv("HOSTINGER_UPLOAD_TOKEN", "").strip()
HOSTINGER_UPLOAD_FIELD = (os.getenv("HOSTINGER_UPLOAD_FIELD", "image") or "image").strip()
HOSTINGER_PUBLIC_BASE_URL = os.getenv("HOSTINGER_PUBLIC_BASE_URL", "").strip()
HOSTINGER_UPLOAD_TIMEOUT = int(os.getenv("HOSTINGER_UPLOAD_TIMEOUT", "60"))

# Allowed image mime types
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

# Max file size: 10 MB
MAX_SIZE_BYTES = 10 * 1024 * 1024


def _to_absolute_remote_url(remote_url: str) -> str:
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
            detail="Remote upload server returned a non-JSON response.",
        ) from exc

    remote_url = _to_absolute_remote_url(data.get("url", ""))
    if not remote_url:
        raise HTTPException(
            status_code=502,
            detail="Remote upload response missing 'url'.",
        )

    return {
        "url": remote_url,
        "filename": data.get("filename") or filename,
        "storage": "remote",
    }


@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    # ── Validate mime type ───────────────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file.content_type}'. Only JPEG, PNG, WEBP allowed."
        )

    # ── Read file and check size ─────────────────────────────────────────────
    contents = await file.read()
    if len(contents) > MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10 MB."
        )

    # ── Generate a unique filename preserving extension ──────────────────────
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    # ── Optional remote forwarding (Hostinger) ──────────────────────────────
    # If HOSTINGER_UPLOAD_URL is set, local file storage is bypassed.
    if HOSTINGER_UPLOAD_URL:
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
                detail=f"Remote upload failed: {exc}",
            ) from exc
        return JSONResponse(payload)

    # ── Save to disk ─────────────────────────────────────────────────────────
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(contents)

    # ── Return local static path (legacy/local mode) ────────────────────────
    return JSONResponse({
        "url": f"/static/images/{filename}",
        "filename": filename,
        "storage": "local",
    })
