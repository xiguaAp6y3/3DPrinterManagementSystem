from fastapi import APIRouter

from app.api.v1.admin_routes import (
    auth as admin_auth,
    custom_requests as admin_custom_requests,
    dashboard,
    files as admin_files,
    inventory,
    orders as admin_orders,
    printers,
    print_tasks,
    production_schedule_items,
    product_categories as admin_product_categories,
    product_images,
    products as admin_products,
    quotes as admin_quotes,
    schedules,
)
from app.api.v1.app_routes import (
    auth as app_auth,
    custom_requests,
    files,
    orders as app_orders,
    product_categories as app_product_categories,
    products as app_products,
    quotes,
)


api_v1_router = APIRouter()

api_v1_router.include_router(app_auth.router, prefix="/app/auth", tags=["app-auth"])
api_v1_router.include_router(app_product_categories.router, prefix="/app/product-categories", tags=["app-product-categories"])
api_v1_router.include_router(app_products.router, prefix="/app/products", tags=["app-products"])
api_v1_router.include_router(app_orders.router, prefix="/app/orders", tags=["app-orders"])
api_v1_router.include_router(files.router, prefix="/app/files", tags=["app-files"])
api_v1_router.include_router(custom_requests.router, prefix="/app/custom-requests", tags=["app-custom-requests"])
api_v1_router.include_router(quotes.router, prefix="/app/quotes", tags=["app-quotes"])

api_v1_router.include_router(admin_auth.router, prefix="/admin/auth", tags=["admin-auth"])
api_v1_router.include_router(dashboard.router, prefix="/admin/dashboard", tags=["admin-dashboard"])
api_v1_router.include_router(admin_product_categories.router, prefix="/admin/product-categories", tags=["admin-product-categories"])
api_v1_router.include_router(admin_products.router, prefix="/admin/products", tags=["admin-products"])
api_v1_router.include_router(admin_orders.router, prefix="/admin/orders", tags=["admin-orders"])
api_v1_router.include_router(admin_custom_requests.router, prefix="/admin/custom-requests", tags=["admin-custom-requests"])
api_v1_router.include_router(admin_quotes.router, prefix="/admin", tags=["admin-quotes"])
api_v1_router.include_router(admin_files.router, prefix="/admin/files", tags=["admin-files"])
api_v1_router.include_router(print_tasks.router, prefix="/admin/print-tasks", tags=["admin-print-tasks"])
api_v1_router.include_router(printers.router, prefix="/admin/printers", tags=["admin-printers"])
api_v1_router.include_router(product_images.router, prefix="/admin/product-images", tags=["admin-product-images"])
api_v1_router.include_router(schedules.router, prefix="/admin/production-schedule-orders", tags=["admin-schedules"])
api_v1_router.include_router(production_schedule_items.router, prefix="/admin/production-schedule-items", tags=["admin-schedule-items"])
api_v1_router.include_router(inventory.router, prefix="/admin/inventory", tags=["admin-inventory"])
