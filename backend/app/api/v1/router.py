from fastapi import APIRouter

from app.api.v1.admin_routes import (
    auth as admin_auth,
    dashboard,
    inventory,
    orders as admin_orders,
    printers,
    products as admin_products,
    schedules,
)
from app.api.v1.app_routes import (
    auth as app_auth,
    custom_requests,
    files,
    orders as app_orders,
    products as app_products,
    quotes,
)


api_v1_router = APIRouter()

api_v1_router.include_router(app_auth.router, prefix="/app/auth", tags=["app-auth"])
api_v1_router.include_router(app_products.router, prefix="/app/products", tags=["app-products"])
api_v1_router.include_router(app_orders.router, prefix="/app/orders", tags=["app-orders"])
api_v1_router.include_router(files.router, prefix="/app/files", tags=["app-files"])
api_v1_router.include_router(custom_requests.router, prefix="/app/custom-requests", tags=["app-custom-requests"])
api_v1_router.include_router(quotes.router, prefix="/app/quotes", tags=["app-quotes"])

api_v1_router.include_router(admin_auth.router, prefix="/admin/auth", tags=["admin-auth"])
api_v1_router.include_router(dashboard.router, prefix="/admin/dashboard", tags=["admin-dashboard"])
api_v1_router.include_router(admin_products.router, prefix="/admin/products", tags=["admin-products"])
api_v1_router.include_router(admin_orders.router, prefix="/admin/orders", tags=["admin-orders"])
api_v1_router.include_router(printers.router, prefix="/admin/printers", tags=["admin-printers"])
api_v1_router.include_router(schedules.router, prefix="/admin/production-schedule-orders", tags=["admin-schedules"])
api_v1_router.include_router(inventory.router, prefix="/admin/inventory", tags=["admin-inventory"])
