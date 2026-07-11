from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from pydantic import BaseModel

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.errors import COMMON_ERROR_RESPONSES, register_exception_handlers
from app.schemas.response import ApiResponse, success_response


class HealthStatus(BaseModel):
    status: str
    env: str


# Swagger UI / ReDoc CDN (cdn.jsdelivr.net 在国内不稳定，换用 unpkg)
SWAGGER_JS = "https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui-bundle.js"
SWAGGER_CSS = "https://unpkg.com/swagger-ui-dist@5.11.0/swagger-ui.css"
REDOC_JS = "https://unpkg.com/redoc@next/bundles/redoc.standalone.js"


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        responses=COMMON_ERROR_RESPONSES,
    )

    # 自定义 docs / redoc 端点，使用可访问的 CDN
    if settings.debug:
        @app.get("/docs", include_in_schema=False)
        async def custom_swagger_ui_html():
            return get_swagger_ui_html(
                openapi_url=app.openapi_url,
                title=f"{settings.app_name} - Swagger UI",
                swagger_js_url=SWAGGER_JS,
                swagger_css_url=SWAGGER_CSS,
            )

        @app.get("/redoc", include_in_schema=False)
        async def custom_redoc_html():
            return get_redoc_html(
                openapi_url=app.openapi_url,
                title=f"{settings.app_name} - ReDoc",
                redoc_js_url=REDOC_JS,
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
