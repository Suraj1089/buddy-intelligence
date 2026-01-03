"""
API routes for bookings.
"""
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import desc, select

from app.api.deps import CurrentUser, SessionDep
from app.booking_models import (
    BookingCreate,
    BookingDB,
    BookingRating,
    BookingsPublic,
    BookingUpdate,
    BookingWithDetails,
    MessageResponse,
    ProviderDB,
    ProviderPublic,
    ServiceDB,
    ServicePublic,
)
from app.core.logging import logger

router = APIRouter(prefix="/bookings", tags=["bookings"])


def generate_booking_number() -> str:
    """Generate a unique booking number."""
    import random
    import string
    prefix = "BK"
    timestamp = datetime.now().strftime("%y%m%d")
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}{timestamp}{random_suffix}"


from app.utils.geocoding import get_coordinates


@router.post("", response_model=BookingWithDetails)
async def create_booking(
    booking_in: BookingCreate,
    current_user: CurrentUser,
    session: SessionDep,
) -> Any:
    """
    Create a new booking.
    Triggers background task for auto-assignment to providers.
    """
    user_id = current_user.id
    user_id = current_user.id
    logger.info({
        "event_type": "booking_flow",
        "event_name": "create_booking_start",
        "user_id": str(user_id),
        "service_id": str(booking_in.service_id)
    })

    # Get service details for estimated price if not provided
    if not booking_in.estimated_price:
        service = session.get(ServiceDB, booking_in.service_id)
        if service:
            booking_in.estimated_price = service.base_price

    # Geocode location
    lat = None
    lon = None
    if booking_in.location:
        lat, lon = await get_coordinates(booking_in.location)
        lat, lon = await get_coordinates(booking_in.location)
        logger.info({
            "event_type": "geocoding",
            "event_name": "location_resolved",
            "location": booking_in.location,
            "coordinates": {"lat": lat, "lon": lon}
        })

    # Generate booking number
    booking_number = generate_booking_number()

    # Create booking data
    booking = BookingDB(
        booking_number=booking_number,
        user_id=user_id,
        service_id=booking_in.service_id,
        service_date=booking_in.service_date,
        service_time=booking_in.service_time,
        location=booking_in.location,
        latitude=lat,
        longitude=lon,
        special_instructions=booking_in.special_instructions,
        estimated_price=booking_in.estimated_price,
        status="awaiting_provider",
        provider_distance="Finding providers...",
    )

    session.add(booking)
    session.commit()
    session.refresh(booking)

    # Trigger background task for provider assignment
    # Note: Task system likely needs refactoring if it uses Supabase client.
    # For now, we attempt to trigger it.
    try:
        from app.tasks.assignment_tasks import process_new_booking
        # process_new_booking.delay(str(booking.id))
        logger.info({
            "event_type": "booking_flow",
            "event_name": "trigger_assignment_task",
            "booking_id": str(booking.id)
        })
        process_new_booking.delay(str(booking.id))
    except Exception as e:
        logger.error({
            "event_type": "booking_flow",
            "event_name": "trigger_assignment_failed",
            "error": str(e),
            "booking_id": str(booking.id)
        })

    # Fetch related service and provider details
    result = _enrich_booking(session, booking)

    return result


@router.get("", response_model=BookingsPublic)
def list_bookings(
    current_user: CurrentUser,
    session: SessionDep,
    status: str | None = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    """
    Get all bookings for the authenticated user.
    """
    user_id = current_user.id

    statement = select(BookingDB).where(BookingDB.user_id == user_id).order_by(desc(BookingDB.created_at))

    if status:
        statement = statement.where(BookingDB.status == status)

    statement = statement.offset(skip).limit(limit)
    bookings_db = session.exec(statement).all()

    # Enrich with service and provider details
    bookings = []
    for booking in bookings_db:
        enriched = _enrich_booking(session, booking)
        bookings.append(enriched)

    return BookingsPublic(data=bookings, count=len(bookings))


@router.get("/{booking_id}", response_model=BookingWithDetails)
def get_booking(
    booking_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> Any:
    """
    Get a specific booking by ID.
    """
    user_id = current_user.id
    booking = session.get(BookingDB, booking_id)

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check if user owns this booking or is the assigned provider
    is_owner = booking.user_id == user_id
    is_provider = False

    if not is_owner:
        statement = select(ProviderDB).where(ProviderDB.user_id == user_id)
        provider = session.exec(statement).first()
        if provider and booking.provider_id == provider.id:
            is_provider = True

    if not is_owner and not is_provider:
        raise HTTPException(status_code=403, detail="Not authorized to view this booking")

    return _enrich_booking(session, booking)


@router.patch("/{booking_id}/status", response_model=BookingWithDetails)
def update_booking_status(
    booking_id: uuid.UUID,
    status_update: BookingUpdate,
    current_user: CurrentUser,
    session: SessionDep,
) -> Any:
    """
    Update booking status.
    """
    user_id = current_user.id
    booking = session.get(BookingDB, booking_id)

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check authorization - user must own the booking or be the assigned provider
    is_owner = booking.user_id == user_id
    is_provider = False

    if not is_owner:
        statement = select(ProviderDB).where(ProviderDB.user_id == user_id)
        provider = session.exec(statement).first()
        if provider and booking.provider_id == provider.id:
            is_provider = True

    if not is_owner and not is_provider:
        raise HTTPException(status_code=403, detail="Not authorized to update this booking")

    # Update fields
    booking.updated_at = datetime.utcnow()

    if status_update.status:
        booking.status = status_update.status.value
    if status_update.final_price is not None:
        booking.final_price = status_update.final_price

    session.add(booking)
    session.commit()
    session.refresh(booking)

    return _enrich_booking(session, booking)


@router.delete("/{booking_id}", response_model=MessageResponse)
def cancel_booking(
    booking_id: uuid.UUID,
    current_user: CurrentUser,
    session: SessionDep,
) -> Any:
    """
    Cancel a booking (set status to cancelled).
    """
    user_id = current_user.id
    booking = session.get(BookingDB, booking_id)

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Only booking owner can cancel
    if booking.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")

    # Check if booking can be cancelled
    if booking.status in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel booking with status: {booking.status}")

    # Cancel the booking
    booking.status = "cancelled"
    booking.updated_at = datetime.utcnow()

    session.add(booking)
    session.commit()

    return MessageResponse(message="Booking cancelled successfully")



@router.post("/{booking_id}/rate", response_model=MessageResponse)
def rate_booking(
    booking_id: uuid.UUID,
    rating_in: BookingRating,
    current_user: CurrentUser,
    session: SessionDep,
) -> Any:
    """Rate a completed booking."""
    user_id = current_user.id
    booking = session.get(BookingDB, booking_id)

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized")

    if booking.status != "completed":
        raise HTTPException(status_code=400, detail="Booking must be completed to rate")

    booking.rating = rating_in.rating
    booking.review_comment = rating_in.comment
    session.add(booking)
    session.commit()

    # Update Provider Rating
    if booking.provider_id:
        from sqlalchemy import func
        statement = select(func.avg(BookingDB.rating)).where(
            BookingDB.provider_id == booking.provider_id,
            BookingDB.rating != None
        )
        avg_rating = session.exec(statement).first()
        
        provider = session.get(ProviderDB, booking.provider_id)
        if provider and avg_rating:
            provider.rating = float(avg_rating)
            session.add(provider)
            session.commit()

    return MessageResponse(message="Rating submitted successfully")


def _enrich_booking(session: SessionDep, booking: BookingDB) -> BookingWithDetails:
    """
    Enrich a booking with service and provider details.
    """
    service = None
    provider = None

    # Fetch service details
    if booking.service_id:
        service_db = session.get(ServiceDB, booking.service_id)
        if service_db:
            service = ServicePublic.model_validate(service_db)

    # Fetch provider details
    if booking.provider_id:
        provider_db = session.get(ProviderDB, booking.provider_id)
        if provider_db:
            provider = ProviderPublic.model_validate(provider_db)

    return BookingWithDetails(
        id=booking.id,
        booking_number=booking.booking_number,
        user_id=booking.user_id,
        service_id=booking.service_id,
        provider_id=booking.provider_id,
        service_date=booking.service_date,
        service_time=booking.service_time,
        location=booking.location,
        special_instructions=booking.special_instructions,
        status=booking.status,
        estimated_price=booking.estimated_price,
        final_price=booking.final_price,
        provider_distance=booking.provider_distance,
        estimated_arrival=booking.estimated_arrival,
        rating=booking.rating,
        review_comment=booking.review_comment,
        created_at=booking.created_at,
        updated_at=booking.updated_at,
        service=service,
        provider=provider,
    )
