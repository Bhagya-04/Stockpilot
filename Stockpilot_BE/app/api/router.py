from fastapi import APIRouter

from app.api.routers import auth, dashboard, inventory, orders, products, workspaces

api_router = APIRouter()
for module in (auth, workspaces, products, inventory, orders, dashboard):
    api_router.include_router(module.router)
