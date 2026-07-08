from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import COMMON_ERROR_RESPONSES, register_exception_handlers
from app.schemas.response import ApiResponse, success_response


class HealthStatus(BaseModel):
    status: str
    env: str


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        responses=COMMON_ERROR_RESPONSES,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id", "Idempotency-Key"],
    )

    register_exception_handlers(app)
    settings.upload_root.mkdir(parents=True, exist_ok=True)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)

    @app.get("/health", tags=["system"], response_model=ApiResponse[HealthStatus])
    def health():
        return success_response({"status": "ok", "env": settings.app_env})

    return app


app = create_app()
