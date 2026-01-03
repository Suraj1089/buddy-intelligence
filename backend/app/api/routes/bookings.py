"""
API routes for bookings.
"""
from typing import Any, Optional
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Depends

from app.core.supabase_client import get_supabase_client
from app.api.deps import CurrentUser
from app.booking_models import (
    BookingCreate,
    BookingUpdate,
    BookingPublic,
    BookingWithDetails,
    BookingsPublic,
    BookingStatus,
    MessageResponse,
    ServicePublic,
    ProviderPublic,
)

router = APIRouter(prefix="/bookings", tags=["bookings"])





def generate_booking_number() -> str:
    """Generate a unique booking number."""
    import random
    import string
    prefix = "BK"
    timestamp = datetime.now().strftime("%y%m%d")
    random_suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"{prefix}{timestamp}{random_suffix}"


@router.post("", response_model=BookingWithDetails)
def create_booking(
    booking_in: BookingCreate,
    current_user: CurrentUser,
) -> Any:
    """
    Create a new booking.
    Triggers background task for auto-assignment to providers.
    """
    user_id = current_user.id
    supabase = get_supabase_client()
    
    # Get service details for estimated price if not provided
    if not booking_in.estimated_price:
        service_response = supabase.table("services").select("base_price").eq("id", str(booking_in.service_id)).single().execute()
        if service_response.data:
            booking_in.estimated_price = service_response.data.get("base_price", 0)
    
    # Generate booking number
    booking_number = generate_booking_number()
    
    # Create booking data
    booking_data = {
        "user_id": str(user_id),
        "service_id": str(booking_in.service_id),
        "service_date": booking_in.service_date,
        "service_time": booking_in.service_time,
        "location": booking_in.location,
        "special_instructions": booking_in.special_instructions or "",
        "estimated_price": booking_in.estimated_price,
        "booking_number": booking_number,
        "status": "awaiting_provider",
        "provider_distance": "Finding providers...",
    }
    
    # Insert booking
    response = supabase.table("bookings").insert(booking_data).execute()
    
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to create booking")
    
    booking = response.data[0]
    
    # Trigger background task for provider assignment
    try:
        from app.tasks.assignment_tasks import process_new_booking
        process_new_booking.delay(booking["id"])
    except Exception as e:
        # Log error but don't fail the booking creation
        print(f"Failed to trigger assignment task: {e}")
    
    # Fetch related service and provider details
    result = _enrich_booking(supabase, booking)
    
    return result


@router.get("", response_model=BookingsPublic)
def list_bookings(
    current_user: CurrentUser,
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    """
    Get all bookings for the authenticated user.
    """
    user_id = current_user.id
    supabase = get_supabase_client()
    
    query = supabase.table("bookings").select("*").eq("user_id", str(user_id)).order("created_at", desc=True)
    
    if status:
        query = query.eq("status", status)
    
    response = query.range(skip, skip + limit - 1).execute()
    
    # Enrich with service and provider details
    bookings = []
    for booking in response.data:
        enriched = _enrich_booking(supabase, booking)
        bookings.append(enriched)
    
    return BookingsPublic(data=bookings, count=len(bookings))


@router.get("/{booking_id}", response_model=BookingWithDetails)
def get_booking(
    booking_id: uuid.UUID,
    current_user: CurrentUser,
) -> Any:
    """
    Get a specific booking by ID.
    """
    user_id = current_user.id
    supabase = get_supabase_client()
    
    response = supabase.table("bookings").select("*").eq("id", str(booking_id)).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking = response.data
    
    # Check if user owns this booking or is the assigned provider
    if booking["user_id"] != str(user_id):
        # Check if user is the provider
        provider_response = supabase.table("providers").select("id").eq("user_id", str(user_id)).single().execute()
        if not provider_response.data or booking.get("provider_id") != provider_response.data["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view this booking")
    
    return _enrich_booking(supabase, booking)


@router.patch("/{booking_id}/status", response_model=BookingWithDetails)
def update_booking_status(
    booking_id: uuid.UUID,
    status_update: BookingUpdate,
    current_user: CurrentUser,
) -> Any:
    """
    Update booking status.
    """
    user_id = current_user.id
    supabase = get_supabase_client()
    
    # Get current booking
    response = supabase.table("bookings").select("*").eq("id", str(booking_id)).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking = response.data
    
    # Check authorization - user must own the booking or be the assigned provider
    is_owner = booking["user_id"] == str(user_id)
    is_provider = False
    
    if not is_owner:
        provider_response = supabase.table("providers").select("id").eq("user_id", str(user_id)).single().execute()
        if provider_response.data and booking.get("provider_id") == provider_response.data["id"]:
            is_provider = True
    
    if not is_owner and not is_provider:
        raise HTTPException(status_code=403, detail="Not authorized to update this booking")
    
    # Prepare update data
    update_data = {"updated_at": datetime.utcnow().isoformat()}
    
    if status_update.status:
        update_data["status"] = status_update.status.value
    if status_update.final_price is not None:
        update_data["final_price"] = status_update.final_price
    
    # Update booking
    update_response = supabase.table("bookings").update(update_data).eq("id", str(booking_id)).execute()
    
    if not update_response.data:
        raise HTTPException(status_code=500, detail="Failed to update booking")
    
    return _enrich_booking(supabase, update_response.data[0])


@router.delete("/{booking_id}", response_model=MessageResponse)
def cancel_booking(
    booking_id: uuid.UUID,
    current_user: CurrentUser,
) -> Any:
    """
    Cancel a booking (set status to cancelled).
    """
    user_id = current_user.id
    supabase = get_supabase_client()
    
    # Get current booking
    response = supabase.table("bookings").select("*").eq("id", str(booking_id)).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking = response.data
    
    # Only booking owner can cancel
    if booking["user_id"] != str(user_id):
        raise HTTPException(status_code=403, detail="Not authorized to cancel this booking")
    
    # Check if booking can be cancelled
    if booking["status"] in ["completed", "cancelled"]:
        raise HTTPException(status_code=400, detail=f"Cannot cancel booking with status: {booking['status']}")
    
    # Cancel the booking
    update_response = supabase.table("bookings").update({
        "status": "cancelled",
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", str(booking_id)).execute()
    
    if not update_response.data:
        raise HTTPException(status_code=500, detail="Failed to cancel booking")
    
    return MessageResponse(message="Booking cancelled successfully")


def _enrich_booking(supabase, booking: dict) -> BookingWithDetails:
    """
    Enrich a booking with service and provider details.
    """
    service = None
    provider = None
    
    # Fetch service details
    if booking.get("service_id"):
        service_response = supabase.table("services").select("*").eq("id", booking["service_id"]).single().execute()
        if service_response.data:
            service = ServicePublic(**service_response.data)
    
    # Fetch provider details
    if booking.get("provider_id"):
        provider_response = supabase.table("providers").select("*").eq("id", booking["provider_id"]).single().execute()
        if provider_response.data:
            provider = ProviderPublic(**provider_response.data)
    
    return BookingWithDetails(
        id=uuid.UUID(booking["id"]),
        booking_number=booking["booking_number"],
        user_id=uuid.UUID(booking["user_id"]),
        service_id=uuid.UUID(booking["service_id"]) if booking.get("service_id") else None,
        provider_id=uuid.UUID(booking["provider_id"]) if booking.get("provider_id") else None,
        service_date=booking["service_date"],
        service_time=booking["service_time"],
        location=booking["location"],
        special_instructions=booking.get("special_instructions"),
        status=booking.get("status"),
        estimated_price=booking.get("estimated_price"),
        final_price=booking.get("final_price"),
        provider_distance=booking.get("provider_distance"),
        estimated_arrival=booking.get("estimated_arrival"),
        created_at=datetime.fromisoformat(booking["created_at"].replace("Z", "+00:00")) if booking.get("created_at") else datetime.utcnow(),
        updated_at=datetime.fromisoformat(booking["updated_at"].replace("Z", "+00:00")) if booking.get("updated_at") else datetime.utcnow(),
        service=service,
        provider=provider,
    )
