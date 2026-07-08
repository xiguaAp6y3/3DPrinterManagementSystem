from datetime import datetime
import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import require_app_user
from app.db.models.core import ModelFile
from app.db.session import get_db
from app.schemas.response import ApiResponse, success_response
from app.services.db_helpers import file_download_url, require_entity, safe_storage_name

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
async def upload_file(file: UploadFile = File(...), current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise AppError("FILE_TYPE_NOT_ALLOWED", "文件类型不允许", status_code=422, details={"ext": suffix})
    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise AppError("FILE_TOO_LARGE", "文件超过大小限制", status_code=413)
    user_id = current_user["user"].id
    directory = settings.upload_root / "model_files" / str(user_id)
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.utcnow():%Y%m%d%H%M%S%f}_{safe_storage_name(file.filename or 'upload')}"
    storage_path = directory / filename
    storage_path.write_bytes(content)
    is_slice_file = suffix in {".gcode", ".3mf", ".bgcode", ".zip"}
    model_file = ModelFile(
        user_id=user_id,
        file_name=file.filename or filename,
        file_ext=suffix,
        file_type="slice" if is_slice_file else "model",
        file_size=len(content),
        storage_key=str(storage_path.as_posix()),
        sha256=hashlib.sha256(content).hexdigest(),
        is_slice_file=is_slice_file,
        upload_status="stored",
        owner_type="user",
        owner_id=user_id,
    )
    db.add(model_file)
    db.commit()
    db.refresh(model_file)
    return success_response(serialize_file(model_file))


@router.get("/{file_id}", response_model=ApiResponse[FileInfo])
def get_file(file_id: int, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    model_file = get_owned_file(db, file_id, current_user["user"].id)
    return success_response(serialize_file(model_file))


@router.get("/{file_id}/download-url", response_model=ApiResponse[DownloadUrl])
def get_download_url(file_id: int, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    get_owned_file(db, file_id, current_user["user"].id)
    return success_response({"file_id": file_id, "download_url": file_download_url("app", file_id), "expires_in_seconds": 300})


@router.get("/{file_id}/download")
def download_file(file_id: int, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    model_file = get_owned_file(db, file_id, current_user["user"].id)
    path = Path(model_file.storage_key)
    if not path.exists() or not path.is_file():
        require_entity(None, "文件不存在")
    return FileResponse(path, filename=model_file.file_name)


@router.delete("/{file_id}", response_model=ApiResponse[dict[str, int | str]])
def delete_file(file_id: int, current_user: dict = Depends(require_app_user), db: Session = Depends(get_db)):
    model_file = get_owned_file(db, file_id, current_user["user"].id)
    model_file.deleted_at = datetime.utcnow()
    db.commit()
    return success_response({"file_id": file_id, "status": "deleted"})


def get_owned_file(db: Session, file_id: int, user_id: int) -> ModelFile:
    return require_entity(
        db.scalar(select(ModelFile).where(ModelFile.id == file_id, ModelFile.user_id == user_id, ModelFile.deleted_at.is_(None))),
        "文件不存在",
    )


def serialize_file(model_file: ModelFile) -> dict:
    return {
        "file_id": model_file.id,
        "file_name": model_file.file_name,
        "file_ext": model_file.file_ext,
        "file_type": model_file.file_type,
        "file_size": model_file.file_size,
        "is_slice_file": model_file.is_slice_file,
        "upload_status": model_file.upload_status,
        "virus_scan_status": model_file.virus_scan_status,
        "analysis_status": model_file.analysis_status,
    }
