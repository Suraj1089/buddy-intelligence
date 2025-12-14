from fastapi import APIRouter

from app.api.routes import items, login, private, users, utils
from app.api.routes import services, bookings, providers, assignments, auth
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)

# Booking system routes
api_router.include_router(services.router)
api_router.include_router(bookings.router)
api_router.include_router(providers.router)
api_router.include_router(assignments.router)

# Auth routes (FastAPI-native, replaces Supabase Auth)
api_router.include_router(auth.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)

