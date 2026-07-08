from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from starlette import status

from app.core.errors import AppError
from app.core.config import settings


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def page_bounds(page: int, page_size: int) -> tuple[int, int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    return page, page_size


def paginate(db: Session, stmt, page: int, page_size: int):
    page, page_size = page_bounds(page, page_size)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    return items, page, page_size, total


def require_entity(entity, message: str = "资源不存在"):
    if entity is None:
        raise AppError("RESOURCE_NOT_FOUND", message, status.HTTP_404_NOT_FOUND)
    return entity


def next_no(db: Session, sequence_name: str, prefix: str) -> str:
    value = db.execute(text(f"SELECT NEXT VALUE FOR dbo.{sequence_name}")).scalar_one()
    return f"{prefix}{date.today():%Y%m%d}{int(value):06d}"


def safe_storage_name(filename: str) -> str:
    return Path(filename).name.replace("\\", "_").replace("/", "_")


def upload_public_url(storage_key: str | None) -> str | None:
    if not storage_key:
        return None
    normalized = storage_key.replace("\\", "/")
    if normalized.startswith(("http://", "https://", "/uploads/")):
        return normalized
    if normalized.startswith("uploads/"):
        return "/" + normalized
    marker = "/uploads/"
    if marker in normalized:
        return marker + normalized.split(marker, 1)[1]
    return normalized


def product_image_public_url(image_id: int | None) -> str | None:
    if image_id is None:
        return None
    return f"/api/v1/public/product-images/{image_id}"


def file_download_url(scope: str, file_id: int | None) -> str | None:
    if file_id is None:
        return None
    return f"/api/v1/{scope}/files/{file_id}/download"


def resolve_storage_path(storage_key: str | None) -> Path | None:
    if not storage_key:
        return None
    path = Path(storage_key)
    if path.exists():
        return path
    if not path.is_absolute():
        for candidate in (settings.upload_root.parent / storage_key, settings.upload_root / storage_key):
            if candidate.exists():
                return candidate
    return path


def storage_file_exists(storage_key: str | None) -> bool:
    path = resolve_storage_path(storage_key)
    return bool(path and path.exists() and path.is_file())
