from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
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

API_DESCRIPTION = """
3DPMS 是面向 3D 打印农场的统一后端 API，覆盖客户账号、上架商品、个性化定制、优惠券、订单、排期、打印、库存、入库、发货和出库。

- `/api/v1/app/*`：Flutter 客户端接口，只能访问当前客户自己的资源。
- `/api/v1/admin/*`：电脑管理端接口，需要管理员 Token。
- `/api/v1/public/*`：无需登录的公开展示资源，目前仅包含商品图片。
- 关键写接口使用 `Idempotency-Key`；统一幂等服务仍在逐步接入。
- 完整流程和状态约束见 `Design/全流程系统与API设计文档.md`。
"""

OPENAPI_TAGS = [
    {"name": "system", "description": "服务健康检查。"},
    {"name": "public-product-images", "description": "无需登录的商品展示图片读取。"},
    {"name": "app-auth", "description": "客户注册、登录、Token、资料和密码管理。"},
    {"name": "app-product-categories", "description": "客户查询启用的商品分类。"},
    {"name": "app-products", "description": "客户浏览上架商品、SKU 和展示图片。"},
    {"name": "app-orders", "description": "客户下单、订单详情和物流查询。"},
    {"name": "app-files", "description": "客户私有模型/切片文件上传、下载和删除。"},
    {"name": "app-custom-requests", "description": "客户个性化定制申请和资料补充。"},
    {"name": "app-quotes", "description": "客户查看和确认定制报价。"},
    {"name": "app-coupons", "description": "客户优惠券列表、抽奖发券和可用状态。"},
    {"name": "admin-auth", "description": "管理员登录、Token 刷新和退出。"},
    {"name": "admin-users", "description": "客户账号查询、维护、禁用和密码重置。"},
    {"name": "admin-staff-users", "description": "管理员账号管理，仅限高权限管理员。"},
    {"name": "admin-dashboard", "description": "生产、订单、库存和异常待办统计。"},
    {"name": "admin-product-categories", "description": "商品分类维护。"},
    {"name": "admin-products", "description": "商品、SKU、销售状态和商品图片管理。"},
    {"name": "admin-product-images", "description": "商品图片独立资源更新和删除。"},
    {"name": "admin-orders", "description": "订单查询、状态维护和线下收款确认。"},
    {"name": "admin-custom-requests", "description": "个性化定制审核和报价入口。"},
    {"name": "admin-quotes", "description": "管理员报价列表和详情。"},
    {"name": "admin-files", "description": "管理员鉴权查看客户模型/切片文件。"},
    {"name": "admin-print-tasks", "description": "打印任务创建、查询和状态推进。"},
    {"name": "admin-printers", "description": "打印机资料和人工状态维护。"},
    {"name": "admin-schedules", "description": "订单生产排期和材料锁定。"},
    {"name": "admin-schedule-items", "description": "排期明细查询和调整。"},
    {"name": "admin-inventory", "description": "材料库存、锁定、释放、消耗和损耗。"},
    {"name": "admin-warehouse", "description": "仓库、库位、成品入库、运单、包裹和批量出库。"},
    {"name": "admin-coupons", "description": "优惠券模板、发放、客户归属查询和作废。"},
]

TAG_OBJECT_LABELS = {
    "system": "系统状态",
    "public-product-images": "公开商品图片",
    "app-auth": "客户认证与资料",
    "app-product-categories": "客户商品分类",
    "app-products": "客户商品",
    "app-orders": "客户订单与物流",
    "app-files": "客户私有文件",
    "app-custom-requests": "客户定制申请",
    "app-quotes": "客户报价",
    "app-coupons": "客户优惠券与抽奖",
    "admin-auth": "管理员认证",
    "admin-users": "客户账号",
    "admin-staff-users": "管理员账号",
    "admin-dashboard": "管理看板",
    "admin-product-categories": "商品分类",
    "admin-products": "商品、SKU 与商品图片",
    "admin-product-images": "商品图片",
    "admin-orders": "订单与收款",
    "admin-custom-requests": "定制审核与报价",
    "admin-quotes": "管理员报价",
    "admin-files": "客户文件",
    "admin-print-tasks": "打印任务",
    "admin-printers": "打印机",
    "admin-schedules": "生产排期",
    "admin-schedule-items": "排期明细",
    "admin-inventory": "材料库存与库存锁",
    "admin-warehouse": "仓库、入库、发货与出库",
    "admin-coupons": "优惠券模板与用户优惠券",
}

METHOD_LABELS = {
    "get": "查询",
    "post": "创建或执行",
    "patch": "更新",
    "put": "更新",
    "delete": "删除",
}


def _operation_description(method: str, path: str, tag: str) -> tuple[str, str]:
    object_label = TAG_OBJECT_LABELS.get(tag, "业务资源")
    action = METHOD_LABELS.get(method, "处理")
    if tag.startswith("app-"):
        permission = "需要客户 Bearer Token，且只能访问当前客户允许访问的资源。"
    elif tag.startswith("admin-"):
        permission = "需要管理员 Bearer Token，并受后台角色权限控制。"
    elif tag == "public-product-images":
        permission = "公开展示接口，不需要登录。"
    else:
        permission = "系统接口，不需要业务身份认证。"
    summary = f"{action}{object_label}"
    description = (
        f"{action}{object_label}。{permission}\n\n"
        f"接口路径：`{path}`\n\n"
        "成功时返回统一的 `ApiResponse` 结构；参数、响应模型和错误码以当前 OpenAPI schema 为准。"
    )
    return summary, description


def build_openapi(app: FastAPI) -> dict:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=OPENAPI_TAGS,
    )
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if method not in METHOD_LABELS:
                continue
            tag = operation.get("tags", ["system"])[0]
            summary, description = _operation_description(method, path, tag)
            operation["summary"] = summary
            operation["description"] = description
    app.openapi_schema = schema
    return app.openapi_schema


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description=API_DESCRIPTION,
        debug=settings.debug,
        version="0.1.0",
        openapi_tags=OPENAPI_TAGS,
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
    app.openapi = lambda: build_openapi(app)

    @app.get("/health", tags=["system"], response_model=ApiResponse[HealthStatus])
    def health():
        return success_response({"status": "ok", "env": settings.app_env})

    return app


app = create_app()
