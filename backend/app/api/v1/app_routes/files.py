from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import require_app_user
from app.schemas.response import ApiResponse, success_response

router = APIRouter()

ALLOWED_EXTENSIONS = {".gcode", ".3mf", ".bgcode", ".zip", ".stl", ".obj", ".step", ".stp", ".fbx"}


class FileInfo(BaseModel):
    file_id: int | None = None
    file_name: str | None = None
    file_ext: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    is_slice_file: bool = False
    upload_status: str = "stored"
    virus_scan_status: str | None = None
    analysis_status: str | None = None


class DownloadUrl(BaseModel):
    file_id: int
    download_url: str
    expires_in_seconds: int = 300


@router.post("/upload", response_model=ApiResponse[FileInfo])
async def upload_file(file: UploadFile = File(...), _: dict = Depends(require_app_user)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise AppError("FILE_TYPE_NOT_ALLOWED", "文件类型不允许", status_code=422, details={"ext": suffix})
    settings.upload_root.mkdir(parents=True, exist_ok=True)
    return success_response({"file_id": None, "file_name": file.filename, "file_ext": suffix, "file_type": "slice" if suffix in {".gcode", ".3mf", ".bgcode", ".zip"} else "model", "is_slice_file": suffix in {".gcode", ".3mf", ".bgcode", ".zip"}, "upload_status": "accepted"})


@router.get("/{file_id}", response_model=ApiResponse[FileInfo])
def get_file(file_id: int, _: dict = Depends(require_app_user)):
    return success_response({"file_id": file_id, "is_slice_file": True, "upload_status": "stored"})


@router.get("/{file_id}/download-url", response_model=ApiResponse[DownloadUrl])
def get_download_url(file_id: int, _: dict = Depends(require_app_user)):
    return success_response({"file_id": file_id, "download_url": f"/api/v1/app/files/{file_id}/download", "expires_in_seconds": 300})


@router.delete("/{file_id}", response_model=ApiResponse[dict[str, int | str]])
def delete_file(file_id: int, _: dict = Depends(require_app_user)):
    return success_response({"file_id": file_id, "status": "deleted"})
