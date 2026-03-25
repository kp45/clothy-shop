# app/routes/upload.py
import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import aiofiles

router = APIRouter(prefix="/upload", tags=["Upload"])

# Folder where images are saved (relative to where uvicorn is started)
UPLOAD_DIR = "static/images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Allowed image mime types
ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

# Max file size: 10 MB
MAX_SIZE_BYTES = 10 * 1024 * 1024


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

    # ── Save to disk ─────────────────────────────────────────────────────────
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(contents)

    # ── Return the public URL path ───────────────────────────────────────────
    # Client combines this with BASE_URL to get the full URL:
    # e.g. http://192.168.1.45:8000/static/images/abc123.jpg
    return JSONResponse({
        "url": f"/static/images/{filename}",
        "filename": filename,
    })