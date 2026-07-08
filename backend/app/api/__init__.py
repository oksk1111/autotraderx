from fastapi import APIRouter

from app.api.routes import account, auth, config, dashboard, earn, health, risk, shadow, strategy

api_router = APIRouter()
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(account.router, prefix="/account", tags=["account"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(strategy.router, prefix="/strategy", tags=["strategy"])
api_router.include_router(risk.router, prefix="/risk", tags=["risk"])
api_router.include_router(shadow.router, prefix="/shadow", tags=["shadow"])
api_router.include_router(earn.router, prefix="/earn", tags=["earn"])
