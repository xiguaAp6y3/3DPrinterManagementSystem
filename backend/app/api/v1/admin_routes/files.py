from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.models.core import ModelFile
from app.db.session import get_db
from app.schemas.response import ApiResponse, success_response
from app.services.db_helpers import file_download_url, require_entity

router = APIRouter()


class AdminFileInfo(BaseModel):
    file_id: int
    user_id: int | None = None
    custom_request_id: int | None = None
    file_name: str | None = None
    file_ext: str | None = None
    file_type: str | None = None
    file_size: int | None = None
    is_slice_file: bool = True
    printer_profile_summary: str | None = None
    upload_status: str = "stored"
    virus_scan_status: str | None = None
    analysis_status: str | None = None
    owner_type: str | None = None
    owner_id: int | None = None


class AdminFileDownloadUrl(BaseModel):
    file_id: int
    download_url: str
    expires_in_seconds: int = 300


@router.get("/{file_id}", response_model=ApiResponse[AdminFileInfo])
def get_file(file_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    model_file = require_entity(db.get(ModelFile, file_id), "文件不存在")
    return success_response(serialize_file(model_file))


@router.get("/{file_id}/download-url", response_model=ApiResponse[AdminFileDownloadUrl])
def get_download_url(file_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    model_file = require_entity(db.get(ModelFile, file_id), "文件不存在")
    return success_response(
        {
            "file_id": file_id,
            "download_url": file_download_url("admin", file_id),
            "expires_in_seconds": 300,
        }
    )


@router.get("/{file_id}/download")
def download_file(file_id: int, _: dict = Depends(require_admin), db: Session = Depends(get_db)):
    model_file = require_entity(db.get(ModelFile, file_id), "文件不存在")
    path = Path(model_file.storage_key)
    if not path.exists() or not path.is_file():
        require_entity(None, "文件不存在")
    return FileResponse(path, filename=model_file.file_name)


def serialize_file(model_file: ModelFile) -> dict:
    return {
        "file_id": model_file.id,
        "user_id": model_file.user_id,
        "custom_request_id": model_file.custom_request_id,
        "file_name": model_file.file_name,
        "file_ext": model_file.file_ext,
        "file_type": model_file.file_type,
        "file_size": model_file.file_size,
        "is_slice_file": model_file.is_slice_file,
        "printer_profile_summary": model_file.printer_profile_summary,
        "upload_status": model_file.upload_status,
        "virus_scan_status": model_file.virus_scan_status,
        "analysis_status": model_file.analysis_status,
        "owner_type": model_file.owner_type,
        "owner_id": model_file.owner_id,
    }
