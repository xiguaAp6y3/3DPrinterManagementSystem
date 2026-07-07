from typing import Any


def success_response(data: Any = None, message: str = "success") -> dict[str, Any]:
    return {
        "code": "OK",
        "message": message,
        "data": data if data is not None else {},
    }


def paginated_response(items: list[Any], page: int, page_size: int, total: int) -> dict[str, Any]:
    return success_response(
        {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
        }
    )
