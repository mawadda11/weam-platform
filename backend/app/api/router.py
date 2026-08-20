from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.care_team import router as care_team_router
from app.api.routes.children import router as children_router
from app.api.routes.goals import router as goals_router
from app.api.routes.health import router as health_router
from app.api.routes.reports import router as reports_router
from app.api.routes.timeline import router as timeline_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(children_router)
api_router.include_router(care_team_router)
api_router.include_router(reports_router)
api_router.include_router(goals_router)
api_router.include_router(timeline_router)
