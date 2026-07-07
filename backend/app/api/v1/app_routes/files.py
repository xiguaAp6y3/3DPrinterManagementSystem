from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import require_app_user
from app.schemas.response import success_response

router = APIRouter()

ALLOWED_EXTENSIONS = {".gcode", ".3mf", ".bgcode", ".zip", ".stl", ".obj", ".step", ".stp", ".fbx"}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), _: dict = Depends(require_app_user)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise AppError("FILE_TYPE_NOT_ALLOWED", "文件类型不允许", status_code=422, details={"ext": suffix})
    settings.upload_root.mkdir(parents=True, exist_ok=True)
    return success_response(
        {
            "file_id": None,
            "file_name": file.filename,
            "file_ext": suffix,
            "is_slice_file": suffix in {".gcode", ".3mf", ".bgcode", ".zip"},
            "upload_status": "accepted",
        }
    )
