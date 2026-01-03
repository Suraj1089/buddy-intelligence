"""
Assignment background tasks for auto-assigning providers to bookings.
"""
import uuid
from datetime import datetime, timedelta
from typing import Any

from celery import shared_task
from sqlmodel import Session, select

from app.booking_models import (
    AssignmentQueueDB,
    BookingDB,
    ProviderDB,
    ProviderServicesDB,
)
from app.core.db import engine
from app.core.logging import logger


@shared_task(bind=True, max_retries=3)
def process_new_booking(self, booking_id: str) -> dict[str, Any]:
    """
    Process a new booking and find matching providers.
    """
    logger.info({
        "event_type": "task_execution",
        "event_name": "process_new_booking_start",
        "booking_id": str(booking_id)
    })
    try:
        with Session(engine) as session:
            # Get the booking
            booking = session.exec(
                select(BookingDB).where(BookingDB.id == uuid.UUID(booking_id))
            ).first()

            if not booking:
                return {"success": False, "error": "Booking not found"}

            # If already assigned, skip
            if booking.provider_id:
                logger.info({
                    "event_type": "task_execution",
                    "event_name": "process_new_booking_skipped",
                    "reason": "already_assigned",
                    "booking_id": str(booking_id)
                })
                return {"success": True, "message": "Booking already assigned"}

            # Find matching providers
            providers = find_matching_providers(session, booking)

            if not providers:
                booking.status = "pending"
                booking.provider_distance = "No providers available"
                session.add(booking)
                session.commit()
                logger.warning({
                    "event_type": "task_execution",
                    "event_name": "process_new_booking_no_providers",
                    "booking_id": str(booking_id)
                })
                return {"success": True, "message": "No providers found", "provider_count": 0}

            # Update booking status
            booking.status = "awaiting_provider"
            booking.provider_distance = "Finding providers..."
            session.add(booking)

            # Create assignments for top providers
            expiry_time = datetime.utcnow() + timedelta(minutes=5)

            for provider_data in providers[:3]:  # Top 3 providers
                assignment = AssignmentQueueDB(
                    id=uuid.uuid4(),
                    booking_id=booking.id,
                    provider_id=provider_data["provider_id"],
                    status="pending",
                    score=provider_data["score"],
                    notified_at=datetime.utcnow(),
                    expires_at=expiry_time,
                    created_at=datetime.utcnow(),
                )
                session.add(assignment)

            session.commit()

            # Trigger notifications (could be separate task)
            notify_providers.delay(booking_id)

            return {
                "success": True,
                "message": f"Found {len(providers)} providers",
                "provider_count": min(len(providers), 3),
            }

    except Exception as e:
        logger.error({
            "event_type": "task_execution",
            "event_name": "process_new_booking_error",
            "error": str(e),
            "booking_id": str(booking_id)
        })
        # Retry on failure
        raise self.retry(exc=e, countdown=5)


@shared_task
def notify_providers(booking_id: str) -> Dict[str, Any]:
    """
    Send notifications to providers about a new booking assignment.
    """
    from app.core.firebase_utils import send_push_notification
    from app.booking_models import AssignmentQueueDB, ProviderDB, BookingDB
    from app.models import UserDeviceDB
    
    with Session(engine) as session:
        # Get booking details
        booking = session.get(BookingDB, booking_id)
        if not booking:
            return {"success": False, "error": "Booking not found"}
            
        # Get pending assignments
        assignments = session.exec(
            select(AssignmentQueueDB).where(
                AssignmentQueueDB.booking_id == booking_id,
                AssignmentQueueDB.status == "pending"
            )
        ).all()
        
        sent_count = 0
        
        for assignment in assignments:
            # Get provider user ID
            provider = session.get(ProviderDB, assignment.provider_id)
            if not provider:
                continue
                
            # Get device tokens for this provider's user
            devices = session.exec(
                select(UserDeviceDB).where(UserDeviceDB.user_id == provider.user_id)
            ).all()
            
            for device in devices:
                logger.info(f"Sending push to provider {provider.business_name} (Device: {device.id})")
                success = send_push_notification(
                    token=device.fcm_token,
                    title="New Service Request!",
                    body=f"New booking available: {booking.booking_number}",
                    data={
                        "booking_id": str(booking_id),
                        "assignment_id": str(assignment.id),
                        "type": "new_assignment"
                    }
                )
                if success:
                    sent_count += 1
                    
    logger.info({
        "event_type": "notification",
        "event_name": "providers_notified",
        "booking_id": str(booking_id),
        "push_sent_count": sent_count
    })
    return {"success": True, "sent_count": sent_count}


@shared_task
def check_expired_assignments() -> dict[str, Any]:
    """
    Periodic task to check and expire old assignments.
    Runs every minute via Celery Beat.
    """
    logger.info("Checking for expired assignments...")
    expired_count = 0

    with Session(engine) as session:
        now = datetime.utcnow()

        # Find expired pending assignments
        expired_assignments = session.exec(
            select(AssignmentQueueDB).where(
                AssignmentQueueDB.status == "pending",
                AssignmentQueueDB.expires_at < now
            )
        ).all()

        for assignment in expired_assignments:
            assignment.status = "expired"
            session.add(assignment)
            expired_count += 1

        session.commit()

        # Check bookings that have all assignments expired
        if expired_count > 0:
            check_bookings_needing_reassignment(session)

    return {"success": True, "expired_count": expired_count}


@shared_task
def process_unassigned_bookings() -> dict[str, Any]:
    """
    Periodic task to find unassigned bookings and trigger assignment.
    Runs every minute via Celery Beat.
    """
    logger.info({
        "event_type": "task_execution",
        "event_name": "process_unassigned_bookings_start"
    })

    triggered_count = 0

    with Session(engine) as session:
        # Find bookings that need a provider but have no pending assignments
        # This acts as a retry mechanism and ensures no booking is left behind
        bookings = session.exec(
            select(BookingDB).where(
                BookingDB.status.in_(["awaiting_provider", "pending"]),
                BookingDB.provider_id.is_(None)
            )
        ).all()

        for booking in bookings:
            # Check if any pending assignments exist for this booking
            pending = session.exec(
                select(AssignmentQueueDB).where(
                    AssignmentQueueDB.booking_id == booking.id,
                    AssignmentQueueDB.status == "pending"
                )
            ).first()

            # If no pending assignments, trigger the assignment process
            if not pending:
                logger.info({
                    "event_type": "assignment_lifecycle",
                    "event_name": "retriggering_assignment",
                    "booking_id": str(booking.id)
                })
                process_new_booking.delay(str(booking.id))
                triggered_count += 1

    logger.info({
        "event_type": "task_execution",
        "event_name": "process_unassigned_bookings_completed",
        "triggered_count": triggered_count
    })

    return {"success": True, "triggered_count": triggered_count}


def check_bookings_needing_reassignment(session: Session) -> None:
    """
    Check for bookings where all assignments expired and update their status.
    """
    # Find bookings in awaiting_provider status with no pending assignments
    bookings = session.exec(
        select(BookingDB).where(
            BookingDB.status == "awaiting_provider",
            BookingDB.provider_id.is_(None)
        )
    ).all()

    for booking in bookings:
        # Check if any pending assignments remain
        pending = session.exec(
            select(AssignmentQueueDB).where(
                AssignmentQueueDB.booking_id == booking.id,
                AssignmentQueueDB.status == "pending"
            )
        ).first()

        if not pending:
            booking.provider_distance = "Searching for more providers..."
            session.add(booking)
            logger.info({
                "event_type": "assignment_lifecycle",
                "event_name": "requeuing_booking",
                "booking_id": str(booking.id),
                "reason": "all_assignments_expired"
            })

    session.commit()


import math


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km using Haversine formula"""
    R = 6371  # Earth radius in km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) * math.sin(dlat / 2) +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) * math.sin(dlon / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def find_matching_providers(session: Session, booking: BookingDB) -> list[dict[str, Any]]:
    """
    Find and score providers for a booking.
    Returns list of {provider_id, score} sorted by score descending.
    """
    # Get providers who offer this service
    provider_services = session.exec(
        select(ProviderServicesDB).where(
            ProviderServicesDB.service_id == booking.service_id
        )
    ).all()

    service_provider_ids = {ps.provider_id for ps in provider_services}

    # Get active providers
    # If no providers offer this service, we will fallback to ALL active providers
    query = select(ProviderDB).where(ProviderDB.is_available == True)

    if service_provider_ids:
        query = query.where(ProviderDB.id.in_(service_provider_ids))

    providers = session.exec(query).all()

    # Fallback: If no providers found with service filter, assume flexibility and get ALL available
    if not providers and service_provider_ids:
        query = select(ProviderDB).where(ProviderDB.is_available == True)
        providers = session.exec(query).all()

    scored_providers = []
    MAX_DISTANCE_KM = 20.0

    for provider in providers:
        distance = None

        # Calculate distance if coordinates available
        if booking.latitude and booking.longitude and provider.latitude and provider.longitude:
            distance = calculate_distance(
                booking.latitude, booking.longitude,
                provider.latitude, provider.longitude
            )

            # Filter matches too far away - DISABLED for now to ensure assignment
            # if distance > MAX_DISTANCE_KM:
            #     continue

        # If booking requires location matching but provider has no location, skip
        elif booking.latitude and (not provider.latitude or not provider.longitude):
            # For now, allow providers without location (assume they cover the area)
            # In production, we might want to be stricter or check service radius
            distance = 0.0

        score = calculate_provider_score(session, provider, booking, distance)
        scored_providers.append({
            "provider_id": provider.id,
            "score": score,
            "distance": distance
        })

    # Sort by score descending
    scored_providers.sort(key=lambda x: x["score"], reverse=True)

    return scored_providers


def calculate_provider_score(
    session: Session,
    provider: ProviderDB,
    booking: BookingDB,
    distance: float | None = None
) -> float:
    """
    Calculate a score for a provider based on multiple factors.
    Higher score = better match.
    """
    score = 0.0

    # Base score for being available
    score += 25.0

    # Rating score (0-20 points based on 0-5 rating)
    if provider.rating:
        score += provider.rating * 4
    else:
        score += 12  # Default rating bonus

    # Service match bonus
    score += 30.0

    # Distance bonus (0-20 points)
    if distance is not None:
        # Closer is better. MAX bonus at 0km, 0 bonus at 20km.
        score += max(0, 20 - distance)

    # Workload penalty - fewer active bookings is better
    active_bookings = session.exec(
        select(BookingDB).where(
            BookingDB.provider_id == provider.id,
            BookingDB.status.in_(["pending", "confirmed", "in_progress"])
        )
    ).all()

    workload_penalty = min(len(active_bookings) * 2, 15)
    score -= workload_penalty

    # Experience bonus
    if provider.experience_years:
        score += min(provider.experience_years, 10)

    return max(score, 0)
