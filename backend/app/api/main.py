from fastapi import APIRouter

from app.api.routes import (
    assignments,
    auth,
    bookings,
    items,
    login,
    notifications,
    private,
    providers,
    services,
    users,
    utils,
)
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
api_router.include_router(notifications.router)

# Auth routes (FastAPI-native, replaces Supabase Auth)
api_router.include_router(auth.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)

