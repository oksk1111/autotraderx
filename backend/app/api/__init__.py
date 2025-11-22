from fastapi import APIRouter

from app.api.routes import health, dashboard, config
from app.api.routes import account

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(account.router, prefix="/account", tags=["account"])
