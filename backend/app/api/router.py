from fastapi import APIRouter

from app.api import admin, health, internal

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(internal.router)
api_router.include_router(admin.router)
