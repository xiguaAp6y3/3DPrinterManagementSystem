from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import require_admin
from app.schemas.response import ApiResponse, success_response

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
def get_file(file_id: int, _: dict = Depends(require_admin)):
    return success_response(
        {
            "file_id": file_id,
            "is_slice_file": True,
            "upload_status": "stored",
        }
    )


@router.get("/{file_id}/download-url", response_model=ApiResponse[AdminFileDownloadUrl])
def get_download_url(file_id: int, _: dict = Depends(require_admin)):
    return success_response(
        {
            "file_id": file_id,
            "download_url": f"/api/v1/admin/files/{file_id}/download",
            "expires_in_seconds": 300,
        }
    )
