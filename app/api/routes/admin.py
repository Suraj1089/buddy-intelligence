"""
API routes for admin operations.
"""

from typing import Any

from fastapi import APIRouter, Depends
from sqlmodel import func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.booking_models import (
    BookingDB,
    ProviderDB,
    ServiceDB,
    StatsPublic,
)
from app.models import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/stats",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=StatsPublic,
)
def get_stats(session: SessionDep) -> Any:
    """
    Get dashboard statistics (Admin only).
    """
    # Counters
    total_users = session.exec(select(func.count(User.id))).one()

    # Active providers (is_available=True)
    active_providers = session.exec(
        select(func.count(ProviderDB.id)).where(ProviderDB.is_available == True)
    ).one()

    # Pending booking requests (status='pending' or 'awaiting_provider')
    pending_requests = session.exec(
        select(func.count(BookingDB.id)).where(
            BookingDB.status.in_(["pending", "awaiting_provider"])
        )
    ).one()

    # Total revenue (sum of final_price for completed bookings)
    total_revenue_result = session.exec(
        select(func.sum(BookingDB.final_price)).where(BookingDB.status == "completed")
    ).one()
    total_revenue = float(total_revenue_result) if total_revenue_result else 0.0

    # Services
    total_services = session.exec(select(func.count(ServiceDB.id))).one()
    # Assuming all services are active for now, or add is_active column later
    active_services = total_services

    # Ongoing bookings
    ongoing_bookings = session.exec(
        select(func.count(BookingDB.id)).where(
            BookingDB.status.in_(["confirmed", "in_progress"])
        )
    ).one()

    # Completed bookings
    completed_bookings = session.exec(
        select(func.count(BookingDB.id)).where(BookingDB.status == "completed")
    ).one()

    return StatsPublic(
        total_users=total_users,
        active_providers=active_providers,
        pending_requests=pending_requests,
        total_revenue=total_revenue,
        total_services=total_services,
        active_services=active_services,
        ongoing_bookings=ongoing_bookings,
        completed_bookings=completed_bookings,
    )
