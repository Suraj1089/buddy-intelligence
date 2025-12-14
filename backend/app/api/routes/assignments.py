"""
API routes for booking assignments (provider accept/decline).
"""
from typing import Any
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header

from app.core.supabase_client import get_supabase_client
from app.booking_models import (
    AssignmentPublic,
    AssignmentWithBooking,
    AssignmentsPublic,
    AssignmentResponse,
    BookingWithDetails,
    ServicePublic,
)

router = APIRouter(prefix="/assignments", tags=["assignments"])


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


def get_provider_id_for_user(supabase, user_id: uuid.UUID) -> uuid.UUID:
    """
    Get provider ID for a user.
    """
    response = supabase.table("providers").select("id").eq("user_id", str(user_id)).single().execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="Provider profile not found")
    
    return uuid.UUID(response.data["id"])


@router.get("/pending", response_model=AssignmentsPublic)
def get_pending_assignments(
    authorization: str = Header(...)
) -> Any:
    """
    Get all pending assignments for the current provider.
    """
    user_id = get_user_id_from_token(authorization)
    supabase = get_supabase_client()
    
    # Get provider ID
    provider_id = get_provider_id_for_user(supabase, user_id)
    
    # Get pending assignments that haven't expired
    response = supabase.table("assignment_queue")\
        .select("*")\
        .eq("provider_id", str(provider_id))\
        .eq("status", "pending")\
        .order("created_at", desc=True)\
        .execute()
    
    # Filter expired assignments and enrich with booking details
    now = datetime.utcnow()
    assignments = []
    
    for assignment in response.data:
        # Check if expired
        if assignment.get("expires_at"):
            expires_at = datetime.fromisoformat(assignment["expires_at"].replace("Z", "+00:00").replace("+00:00", ""))
            if expires_at < now:
                # Mark as expired in database
                supabase.table("assignment_queue").update({"status": "expired"}).eq("id", assignment["id"]).execute()
                continue
        
        # Enrich with booking details
        enriched = _enrich_assignment(supabase, assignment)
        if enriched.booking:  # Only include if booking exists
            assignments.append(enriched)
    
    return AssignmentsPublic(data=assignments, count=len(assignments))


@router.post("/{assignment_id}/accept", response_model=AssignmentResponse)
def accept_assignment(
    assignment_id: uuid.UUID,
    authorization: str = Header(...)
) -> Any:
    """
    Accept a booking assignment.
    This will assign the booking to the provider and decline other pending assignments.
    """
    user_id = get_user_id_from_token(authorization)
    supabase = get_supabase_client()
    
    # Get provider ID
    provider_id = get_provider_id_for_user(supabase, user_id)
    
    # Get the assignment
    assignment_response = supabase.table("assignment_queue")\
        .select("*")\
        .eq("id", str(assignment_id))\
        .single()\
        .execute()
    
    if not assignment_response.data:
        return AssignmentResponse(success=False, error="Assignment not found")
    
    assignment = assignment_response.data
    
    # Verify provider owns this assignment
    if assignment["provider_id"] != str(provider_id):
        return AssignmentResponse(success=False, error="Unauthorized")
    
    # Check if already processed
    if assignment["status"] != "pending":
        return AssignmentResponse(success=False, error=f"Assignment already {assignment['status']}")
    
    # Check if assignment expired
    if assignment.get("expires_at"):
        expires_at = datetime.fromisoformat(assignment["expires_at"].replace("Z", "+00:00").replace("+00:00", ""))
        if expires_at < datetime.utcnow():
            supabase.table("assignment_queue").update({"status": "expired"}).eq("id", str(assignment_id)).execute()
            return AssignmentResponse(success=False, error="Assignment has expired")
    
    # Check if booking already assigned
    booking_response = supabase.table("bookings")\
        .select("*")\
        .eq("id", assignment["booking_id"])\
        .single()\
        .execute()
    
    if not booking_response.data:
        return AssignmentResponse(success=False, error="Booking not found")
    
    booking = booking_response.data
    
    if booking.get("provider_id"):
        return AssignmentResponse(success=False, error="Booking already assigned to another provider")
    
    # Accept the assignment
    supabase.table("assignment_queue").update({
        "status": "accepted",
        "responded_at": datetime.utcnow().isoformat()
    }).eq("id", str(assignment_id)).execute()
    
    # Decline all other pending assignments for this booking
    supabase.table("assignment_queue").update({
        "status": "declined",
        "responded_at": datetime.utcnow().isoformat()
    }).eq("booking_id", assignment["booking_id"])\
      .neq("id", str(assignment_id))\
      .eq("status", "pending")\
      .execute()
    
    # Generate distance estimate
    import random
    estimated_distance = round(random.uniform(1, 15), 1)
    
    # Calculate estimated arrival
    arrival_minutes = random.randint(30, 120)
    
    # Update the booking with the provider
    supabase.table("bookings").update({
        "provider_id": str(provider_id),
        "status": "confirmed",
        "provider_distance": f"{estimated_distance} miles",
        "estimated_arrival": f"{arrival_minutes} minutes",
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", assignment["booking_id"]).execute()
    
    return AssignmentResponse(
        success=True,
        message="Booking accepted successfully",
        booking_id=uuid.UUID(assignment["booking_id"])
    )


@router.post("/{assignment_id}/decline", response_model=AssignmentResponse)
def decline_assignment(
    assignment_id: uuid.UUID,
    authorization: str = Header(...)
) -> Any:
    """
    Decline a booking assignment.
    """
    user_id = get_user_id_from_token(authorization)
    supabase = get_supabase_client()
    
    # Get provider ID
    provider_id = get_provider_id_for_user(supabase, user_id)
    
    # Get the assignment
    assignment_response = supabase.table("assignment_queue")\
        .select("*")\
        .eq("id", str(assignment_id))\
        .single()\
        .execute()
    
    if not assignment_response.data:
        return AssignmentResponse(success=False, error="Assignment not found")
    
    assignment = assignment_response.data
    
    # Verify provider owns this assignment
    if assignment["provider_id"] != str(provider_id):
        return AssignmentResponse(success=False, error="Unauthorized")
    
    # Check if already processed
    if assignment["status"] != "pending":
        return AssignmentResponse(success=False, error=f"Assignment already {assignment['status']}")
    
    # Decline the assignment
    supabase.table("assignment_queue").update({
        "status": "declined",
        "responded_at": datetime.utcnow().isoformat()
    }).eq("id", str(assignment_id)).execute()
    
    # Check if there are remaining pending assignments for this booking
    remaining_response = supabase.table("assignment_queue")\
        .select("id")\
        .eq("booking_id", assignment["booking_id"])\
        .eq("status", "pending")\
        .execute()
    
    # If no remaining pending assignments, update booking status
    if not remaining_response.data or len(remaining_response.data) == 0:
        supabase.table("bookings").update({
            "provider_distance": "Searching for more providers...",
            "updated_at": datetime.utcnow().isoformat()
        }).eq("id", assignment["booking_id"]).is_("provider_id", "null").execute()
    
    return AssignmentResponse(success=True, message="Assignment declined")


def _enrich_assignment(supabase, assignment: dict) -> AssignmentWithBooking:
    """
    Enrich an assignment with booking and service details.
    """
    booking_with_details = None
    
    # Fetch booking details
    if assignment.get("booking_id"):
        booking_response = supabase.table("bookings")\
            .select("*")\
            .eq("id", assignment["booking_id"])\
            .single()\
            .execute()
        
        if booking_response.data:
            booking = booking_response.data
            
            # Fetch service details
            service = None
            if booking.get("service_id"):
                service_response = supabase.table("services")\
                    .select("*")\
                    .eq("id", booking["service_id"])\
                    .single()\
                    .execute()
                if service_response.data:
                    service = ServicePublic(**service_response.data)
            
            booking_with_details = BookingWithDetails(
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
                provider=None,
            )
    
    return AssignmentWithBooking(
        id=uuid.UUID(assignment["id"]),
        booking_id=uuid.UUID(assignment["booking_id"]),
        provider_id=uuid.UUID(assignment["provider_id"]),
        status=assignment["status"],
        score=assignment.get("score"),
        notified_at=datetime.fromisoformat(assignment["notified_at"].replace("Z", "+00:00")) if assignment.get("notified_at") else None,
        expires_at=datetime.fromisoformat(assignment["expires_at"].replace("Z", "+00:00")) if assignment.get("expires_at") else None,
        booking=booking_with_details,
    )
