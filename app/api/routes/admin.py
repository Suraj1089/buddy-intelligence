"""
API routes for admin operations.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.api.deps import SessionDep, get_current_active_superuser
from app.booking_models import (
    AdminBookingUpdate,
    AdminProviderCreate,
    AdminProviderUpdate,
    BookingDB,
    ProfileDB,
    ProviderDB,
    ProviderPublic,
    ProvidersPublic,
    ServiceDB,
    StatsPublic,
)
from app.core.security import get_password_hash
from app.models import AdminUserCreate, AdminUserUpdate, User, UserPublic, UsersPublic

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


# ============== USER MANAGEMENT ==============


@router.post(
    "/users",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def admin_create_user(data: AdminUserCreate, session: SessionDep) -> Any:
    """
    Create a new user (Admin only).
    """
    # Check if email already exists
    existing = session.exec(select(User).where(User.email == data.email)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # Create user
    user = User(
        id=uuid.uuid4(),
        email=data.email,
        hashed_password=get_password_hash(data.password),
        full_name=data.full_name,
        is_active=data.is_active,
        is_superuser=data.is_superuser,
    )
    session.add(user)

    # Create profile
    profile = ProfileDB(
        id=uuid.uuid4(),
        user_id=user.id,
        full_name=data.full_name,
    )
    session.add(profile)

    session.commit()
    session.refresh(user)

    return user


@router.patch(
    "/users/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UserPublic,
)
def admin_update_user(user_id: uuid.UUID, data: AdminUserUpdate, session: SessionDep) -> Any:
    """
    Update a user (Admin only).
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)

    # Handle password update
    if "password" in update_data and update_data["password"]:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))
    elif "password" in update_data:
        del update_data["password"]

    for key, value in update_data.items():
        setattr(user, key, value)

    # Also update profile full_name if provided
    if data.full_name is not None:
        profile = session.exec(
            select(ProfileDB).where(ProfileDB.user_id == user_id)
        ).first()
        if profile:
            profile.full_name = data.full_name
            session.add(profile)

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


@router.delete(
    "/users/{user_id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def admin_delete_user(user_id: uuid.UUID, session: SessionDep) -> Any:
    """
    Delete a user (Admin only). Sets is_active to False instead of hard delete.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    session.add(user)
    session.commit()

    return {"message": "User deactivated successfully"}


# ============== PROVIDER MANAGEMENT ==============


@router.post(
    "/providers",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProviderPublic,
)
def admin_create_provider(data: AdminProviderCreate, session: SessionDep) -> Any:
    """
    Create a new provider (Admin only).
    """
    # Check if user exists
    user = session.get(User, data.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if provider already exists for this user
    existing = session.exec(
        select(ProviderDB).where(ProviderDB.user_id == data.user_id)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Provider already exists for this user")

    provider = ProviderDB(
        id=uuid.uuid4(),
        user_id=data.user_id,
        business_name=data.business_name,
        description=data.description,
        email=data.email or user.email,
        phone=data.phone,
        address=data.address,
        city=data.city,
        is_available=data.is_available,
        latitude=data.latitude,
        longitude=data.longitude,
        pincode=data.pincode,
    )
    session.add(provider)
    session.commit()
    session.refresh(provider)

    return provider


@router.patch(
    "/providers/{provider_id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProviderPublic,
)
def admin_update_provider(
    provider_id: uuid.UUID, data: AdminProviderUpdate, session: SessionDep
) -> Any:
    """
    Update a provider (Admin only).
    """
    provider = session.get(ProviderDB, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(provider, key, value)

    provider.updated_at = datetime.utcnow()
    session.add(provider)
    session.commit()
    session.refresh(provider)

    return provider


@router.get(
    "/providers",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProvidersPublic,
)
def admin_list_providers(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> Any:
    """
    List all providers (Admin only).
    """
    providers = session.exec(select(ProviderDB).offset(skip).limit(limit)).all()
    count = session.exec(select(func.count(ProviderDB.id))).one()

    return ProvidersPublic(data=providers, count=count)


# ============== BOOKING MANAGEMENT ==============


@router.patch(
    "/bookings/{booking_id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def admin_update_booking(
    booking_id: uuid.UUID, data: AdminBookingUpdate, session: SessionDep
) -> Any:
    """
    Update a booking (Admin only).
    """
    from datetime import date as date_type

    booking = session.get(BookingDB, booking_id)
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    update_data = data.model_dump(exclude_unset=True)

    # Handle service_date conversion
    if "service_date" in update_data and update_data["service_date"]:
        update_data["service_date"] = date_type.fromisoformat(update_data["service_date"])

    for key, value in update_data.items():
        setattr(booking, key, value)

    booking.updated_at = datetime.utcnow()
    session.add(booking)
    session.commit()
    session.refresh(booking)

    # Return enriched booking
    service = session.get(ServiceDB, booking.service_id) if booking.service_id else None
    provider = session.get(ProviderDB, booking.provider_id) if booking.provider_id else None

    return {
        **booking.model_dump(),
        "service": service.model_dump() if service else None,
        "provider": provider.model_dump() if provider else None,
    }

