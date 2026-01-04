"""
API routes for booking assignments (provider accept/decline).
"""

import random
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep, get_current_user
from app.booking_models import (
    AssignmentQueueDB,
    AssignmentResponse,
    AssignmentsPublic,
    AssignmentWithBooking,
    BookingDB,
    BookingWithDetails,
    ProviderDB,
    ServiceDB,
    ServicePublic,
)
from app.core.logging import logger
from app.models import User

router = APIRouter(prefix="/assignments", tags=["assignments"])


def get_provider_id_for_user(session: SessionDep, user_id: uuid.UUID) -> uuid.UUID:
    """
    Get provider ID for a user.
    """
    statement = select(ProviderDB).where(ProviderDB.user_id == user_id)
    provider = session.exec(statement).first()

    if not provider:
        raise HTTPException(status_code=404, detail="Provider profile not found")

    return provider.id


@router.get("/pending", response_model=AssignmentsPublic)
def get_pending_assignments(
    session: SessionDep, current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get all pending assignments for the current provider.
    """
    # Get provider ID
    provider_id = get_provider_id_for_user(session, current_user.id)
    logger.info(
        {
            "event_type": "assignment_flow",
            "event_name": "fetch_pending_assignments",
            "provider_id": str(provider_id),
        }
    )

    # Get pending assignments
    statement = (
        select(AssignmentQueueDB)
        .where(
            AssignmentQueueDB.provider_id == provider_id,
            AssignmentQueueDB.status == "pending",
        )
        .order_by(AssignmentQueueDB.created_at.desc())
    )  # type: ignore

    assignments_db = session.exec(statement).all()

    logger.info(
        f"DEBUG: Found {len(assignments_db)} pending assignments for provider {provider_id}"
    )
    for a in assignments_db:
        logger.info(
            f"DEBUG: Pending Assignment ID: {a.id}, Status: {a.status}, Expires At: {a.expires_at}"
        )

    # Filter expired assignments and enrich with booking details
    now = datetime.utcnow()
    assignments = []

    for assignment in assignments_db:
        # Check if expired
        if assignment.expires_at and assignment.expires_at < now:
            # Mark as expired
            assignment.status = "expired"
            session.add(assignment)
            session.commit()
            logger.info(
                {
                    "event_type": "assignment_lifecycle",
                    "event_name": "assignment_expired_check",
                    "assignment_id": str(assignment.id),
                    "reason": "expired_during_fetch",
                }
            )
            continue

        # Enrich with booking details
        enriched = _enrich_assignment(session, assignment)
        if enriched.booking:
            assignments.append(enriched)
        else:
            logger.warning(
                f"DEBUG: Booking missing for assignment {assignment.id} (Booking ID: {assignment.booking_id})"
            )

    logger.info(f"DEBUG: Returning {len(assignments)} assignments")
    return AssignmentsPublic(data=assignments, count=len(assignments))


@router.post("/{assignment_id}/accept", response_model=AssignmentResponse)
def accept_assignment(
    assignment_id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Accept a booking assignment.
    This will assign the booking to the provider and decline other pending assignments.
    """
    # Get provider ID
    provider_id = get_provider_id_for_user(session, current_user.id)
    logger.info(
        {
            "event_type": "assignment_flow",
            "event_name": "accept_assignment_attempt",
            "provider_id": str(provider_id),
            "assignment_id": str(assignment_id),
        }
    )

    # Get the assignment
    assignment = session.get(AssignmentQueueDB, assignment_id)

    if not assignment:
        return AssignmentResponse(success=False, error="Assignment not found")

    # Verify provider owns this assignment
    if assignment.provider_id != provider_id:
        return AssignmentResponse(success=False, error="Unauthorized")

    # Check if already processed
    if assignment.status != "pending":
        return AssignmentResponse(
            success=False, error=f"Assignment already {assignment.status}"
        )

    # Check if assignment expired
    if assignment.expires_at and assignment.expires_at < datetime.utcnow():
        assignment.status = "expired"
        session.add(assignment)
        session.commit()
        return AssignmentResponse(success=False, error="Assignment has expired")

    # Check if booking already assigned
    booking = session.get(BookingDB, assignment.booking_id)

    if not booking:
        return AssignmentResponse(success=False, error="Booking not found")

    if booking.provider_id:
        return AssignmentResponse(
            success=False, error="Booking already assigned to another provider"
        )

    # Accept the assignment
    assignment.status = "accepted"
    assignment.responded_at = datetime.utcnow()
    session.add(assignment)

    # Decline all other pending assignments for this booking
    statement = select(AssignmentQueueDB).where(
        AssignmentQueueDB.booking_id == assignment.booking_id,
        AssignmentQueueDB.id != assignment_id,
        AssignmentQueueDB.status == "pending",
    )
    other_assignments = session.exec(statement).all()
    for other in other_assignments:
        other.status = "declined"
        other.responded_at = datetime.utcnow()
        session.add(other)

    # Generate distance estimate
    estimated_distance = round(random.uniform(1, 15), 1)
    # Calculate estimated arrival
    arrival_minutes = random.randint(30, 120)

    # Update the booking with the provider
    booking.provider_id = provider_id
    booking.status = "confirmed"
    booking.provider_distance = f"{estimated_distance} miles"
    booking.estimated_arrival = f"{arrival_minutes} minutes"
    booking.updated_at = datetime.utcnow()
    session.add(booking)

    session.commit()
    session.commit()
    logger.info(
        {
            "event_type": "assignment_flow",
            "event_name": "assignment_accepted",
            "booking_id": str(assignment.booking_id),
            "provider_id": str(provider_id),
            "assignment_id": str(assignment.id),
        }
    )

    return AssignmentResponse(
        success=True,
        message="Booking accepted successfully",
        booking_id=assignment.booking_id,
    )


@router.post("/{assignment_id}/decline", response_model=AssignmentResponse)
def decline_assignment(
    assignment_id: uuid.UUID,
    session: SessionDep,
    current_user: User = Depends(get_current_user),
) -> Any:
    """
    Decline a booking assignment.
    """
    # Get provider ID
    provider_id = get_provider_id_for_user(session, current_user.id)
    logger.info(
        {
            "event_type": "assignment_flow",
            "event_name": "decline_assignment",
            "provider_id": str(provider_id),
            "assignment_id": str(assignment_id),
        }
    )

    # Get the assignment
    assignment = session.get(AssignmentQueueDB, assignment_id)

    if not assignment:
        return AssignmentResponse(success=False, error="Assignment not found")

    # Verify provider owns this assignment
    if assignment.provider_id != provider_id:
        return AssignmentResponse(success=False, error="Unauthorized")

    # Check if already processed
    if assignment.status != "pending":
        return AssignmentResponse(
            success=False, error=f"Assignment already {assignment.status}"
        )

    # Decline the assignment
    assignment.status = "declined"
    assignment.responded_at = datetime.utcnow()
    session.add(assignment)
    session.commit()

    # Check if there are remaining pending assignments for this booking
    statement = select(AssignmentQueueDB).where(
        AssignmentQueueDB.booking_id == assignment.booking_id,
        AssignmentQueueDB.status == "pending",
    )
    remaining_count = len(session.exec(statement).all())

    # If no remaining pending assignments, update booking status
    if remaining_count == 0:
        booking = session.get(BookingDB, assignment.booking_id)
        if booking and not booking.provider_id:
            booking.provider_distance = "Searching for more providers..."
            booking.updated_at = datetime.utcnow()
            session.add(booking)
            session.commit()

    return AssignmentResponse(success=True, message="Assignment declined")


def _enrich_assignment(
    session: SessionDep, assignment: AssignmentQueueDB
) -> AssignmentWithBooking:
    """
    Enrich an assignment with booking and service details.
    """
    booking_with_details = None

    booking = session.get(BookingDB, assignment.booking_id)
    if booking:
        service = None
        if booking.service_id:
            service_db = session.get(ServiceDB, booking.service_id)
            if service_db:
                service = ServicePublic.model_validate(service_db)

        booking_with_details = BookingWithDetails(
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
            created_at=booking.created_at,
            updated_at=booking.updated_at,
            service=service,
            provider=None,
        )

    return AssignmentWithBooking(
        id=assignment.id,
        booking_id=assignment.booking_id,
        provider_id=assignment.provider_id,
        status=assignment.status,
        score=assignment.score,
        notified_at=assignment.notified_at,
        expires_at=assignment.expires_at,
        booking=booking_with_details,
    )
