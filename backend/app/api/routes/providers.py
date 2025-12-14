"""
API routes for providers.
"""
from typing import Any, Optional
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Header

from app.core.supabase_client import get_supabase_client
from app.booking_models import (
    ProviderPublic,
    ProviderUpdate,
    BookingWithDetails,
    BookingsPublic,
    MessageResponse,
    ServicePublic,
)

router = APIRouter(prefix="/providers", tags=["providers"])


def get_user_id_from_token(authorization: str = Header(...)) -> uuid.UUID:
    """
    Extract user ID from Supabase JWT token in Authorization header.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    supabase = get_supabase_client()
    
    try:
        user = supabase.auth.get_user(token)
        if not user or not user.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        return uuid.UUID(user.user.id)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


def get_provider_by_user_id(supabase, user_id: uuid.UUID) -> dict:
    """
    Get provider profile for a user.
    """
    response = supabase.table("providers").select("*").eq("user_id", str(user_id)).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    
    return response.data


@router.get("/me", response_model=ProviderPublic)
def get_current_provider(
    authorization: str = Header(...)
) -> Any:
    """
    Get the current provider's profile.
    """
    user_id = get_user_id_from_token(authorization)
    supabase = get_supabase_client()
    
    provider = get_provider_by_user_id(supabase, user_id)
    
    return ProviderPublic(**provider)


@router.patch("/me", response_model=ProviderPublic)
def update_current_provider(
    provider_update: ProviderUpdate,
    authorization: str = Header(...)
) -> Any:
    """
    Update the current provider's profile.
    """
    user_id = get_user_id_from_token(authorization)
    supabase = get_supabase_client()
    
    # Get current provider
    provider = get_provider_by_user_id(supabase, user_id)
    
    # Prepare update data
    update_data = {"updated_at": datetime.utcnow().isoformat()}
    
    if provider_update.business_name is not None:
        update_data["business_name"] = provider_update.business_name
    if provider_update.description is not None:
        update_data["description"] = provider_update.description
    if provider_update.email is not None:
        update_data["email"] = provider_update.email
    if provider_update.phone is not None:
        update_data["phone"] = provider_update.phone
    if provider_update.address is not None:
        update_data["address"] = provider_update.address
    if provider_update.city is not None:
        update_data["city"] = provider_update.city
    if provider_update.is_available is not None:
        update_data["is_available"] = provider_update.is_available
    
    # Update provider
    response = supabase.table("providers").update(update_data).eq("id", provider["id"]).execute()
    
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to update provider profile")
    
    return ProviderPublic(**response.data[0])


@router.get("/me/bookings", response_model=BookingsPublic)
def get_provider_bookings(
    authorization: str = Header(...),
    status: Optional[str] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
) -> Any:
    """
    Get all bookings assigned to the current provider.
    """
    user_id = get_user_id_from_token(authorization)
    supabase = get_supabase_client()
    
    # Get provider ID
    provider = get_provider_by_user_id(supabase, user_id)
    provider_id = provider["id"]
    
    # Query bookings assigned to this provider
    query = supabase.table("bookings").select("*").eq("provider_id", str(provider_id)).order("created_at", desc=True)
    
    if status:
        query = query.eq("status", status)
    
    response = query.range(skip, skip + limit - 1).execute()
    
    # Enrich with service and user details
    bookings = []
    for booking in response.data:
        enriched = _enrich_provider_booking(supabase, booking)
        bookings.append(enriched)
    
    return BookingsPublic(data=bookings, count=len(bookings))


@router.get("/{provider_id}", response_model=ProviderPublic)
def get_provider(
    provider_id: uuid.UUID
) -> Any:
    """
    Get a provider by ID (public).
    """
    supabase = get_supabase_client()
    
    response = supabase.table("providers").select("*").eq("id", str(provider_id)).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    return ProviderPublic(**response.data)


def _enrich_provider_booking(supabase, booking: dict) -> BookingWithDetails:
    """
    Enrich a booking with service details for provider view.
    """
    service = None
    
    # Fetch service details
    if booking.get("service_id"):
        service_response = supabase.table("services").select("*").eq("id", booking["service_id"]).single().execute()
        if service_response.data:
            service = ServicePublic(**service_response.data)
    
    # For provider view, we might also want user profile info
    # Fetch from profiles table
    user_profile = None
    if booking.get("user_id"):
        profile_response = supabase.table("profiles").select("*").eq("user_id", booking["user_id"]).single().execute()
        # We don't have a schema for profile, but could add it
    
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
        provider=None,  # Not needed for provider's own bookings view
    )
