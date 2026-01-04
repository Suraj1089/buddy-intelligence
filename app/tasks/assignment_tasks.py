"""
Assignment background tasks for auto-assigning providers to bookings.
"""

import uuid
from datetime import datetime, timedelta
from typing import Any, Dict

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
    logger.info(
        {
            "event_type": "task_execution",
            "event_name": "process_new_booking_start",
            "booking_id": str(booking_id),
        }
    )
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
                logger.info(
                    {
                        "event_type": "task_execution",
                        "event_name": "process_new_booking_skipped",
                        "reason": "already_assigned",
                        "booking_id": str(booking_id),
                    }
                )
                return {"success": True, "message": "Booking already assigned"}

            # Find matching providers
            providers = find_matching_providers(session, booking)

            if not providers:
                booking.status = "pending"
                booking.provider_distance = "No providers available"
                session.add(booking)
                session.commit()
                logger.warning(
                    {
                        "event_type": "task_execution",
                        "event_name": "process_new_booking_no_providers",
                        "booking_id": str(booking_id),
                    }
                )
                return {
                    "success": True,
                    "message": "No providers found",
                    "provider_count": 0,
                }

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

            logger.info(
                {
                    "event_type": "assignment_lifecycle",
                    "event_name": "assignments_created",
                    "booking_id": str(booking_id),
                    "provider_count": min(len(providers), 3),
                    "top_providers": [
                        {
                            "provider_id": str(p["provider_id"]),
                            "score": p["score"],
                            "distance": p.get("distance"),
                        }
                        for p in providers[:3]
                    ],
                }
            )

            return {
                "success": True,
                "message": f"Found {len(providers)} providers",
                "provider_count": min(len(providers), 3),
            }

    except Exception as e:
        logger.error(
            {
                "event_type": "task_execution",
                "event_name": "process_new_booking_error",
                "error": str(e),
                "booking_id": str(booking_id),
            }
        )
        # Retry on failure
        raise self.retry(exc=e, countdown=5)


@shared_task
def notify_providers(booking_id: str) -> Dict[str, Any]:
    """
    Send notifications to providers about a new booking assignment.
    """
    from app.core.firebase_utils import send_push_notification
    from app.booking_models import AssignmentQueueDB, ProviderDB, BookingDB, ServiceDB
    from app.models import UserDeviceDB

    logger.info(
        {
            "event_type": "notification",
            "event_name": "notify_providers_start",
            "booking_id": str(booking_id),
        }
    )

    with Session(engine) as session:
        # Get booking details
        booking = session.get(BookingDB, uuid.UUID(booking_id))
        if not booking:
            logger.error(
                {
                    "event_type": "notification",
                    "event_name": "booking_not_found",
                    "booking_id": str(booking_id),
                }
            )
            return {"success": False, "error": "Booking not found"}

        # Get service details for richer notification
        service = (
            session.get(ServiceDB, booking.service_id) if booking.service_id else None
        )
        service_name = service.name if service else "Service"

        # Extract location info (city/area from full address)
        location_short = (
            booking.location.split(",")[0] if booking.location else "Your area"
        )
        estimated_earnings = (
            f"₹{int(booking.estimated_price or 0)}" if booking.estimated_price else ""
        )

        # Get pending assignments
        assignments = session.exec(
            select(AssignmentQueueDB).where(
                AssignmentQueueDB.booking_id == uuid.UUID(booking_id),
                AssignmentQueueDB.status == "pending",
            )
        ).all()

        logger.info(
            {
                "event_type": "notification",
                "event_name": "assignments_found",
                "booking_id": str(booking_id),
                "assignment_count": len(assignments),
                "assignment_ids": [str(a.id) for a in assignments],
            }
        )

        sent_count = 0
        failed_count = 0

        for assignment in assignments:
            # Get provider user ID
            provider = session.get(ProviderDB, assignment.provider_id)
            if not provider:
                logger.warning(
                    {
                        "event_type": "notification",
                        "event_name": "provider_not_found",
                        "provider_id": str(assignment.provider_id),
                    }
                )
                continue

            # Get device tokens for this provider's user
            devices = session.exec(
                select(UserDeviceDB).where(UserDeviceDB.user_id == provider.user_id)
            ).all()

            logger.info(
                {
                    "event_type": "notification",
                    "event_name": "provider_devices_found",
                    "provider_id": str(provider.id),
                    "provider_name": provider.business_name,
                    "user_id": str(provider.user_id),
                    "device_count": len(devices),
                    "device_ids": [str(d.id) for d in devices],
                    "has_fcm_tokens": len([d for d in devices if d.fcm_token]) > 0,
                }
            )

            if not devices:
                logger.warning(
                    {
                        "event_type": "notification",
                        "event_name": "no_devices_registered",
                        "provider_id": str(provider.id),
                        "provider_name": provider.business_name,
                    }
                )
                continue

            # Build rich notification
            title = f"🔔 New {service_name} Request!"
            body_parts = [f"Location: {location_short}"]
            if estimated_earnings:
                body_parts.append(f"Earn: {estimated_earnings}")
            body_parts.append("Tap to view details")
            body = " • ".join(body_parts)

            for device in devices:
                logger.info(
                    {
                        "event_type": "notification",
                        "event_name": "sending_push",
                        "provider_name": provider.business_name,
                        "device_id": str(device.id),
                        "fcm_token_prefix": device.fcm_token[:20]
                        if device.fcm_token
                        else "NONE",
                        "title": title,
                        "body": body,
                    }
                )
                success = send_push_notification(
                    token=device.fcm_token,
                    title=title,
                    body=body,
                    data={
                        "booking_id": str(booking_id),
                        "assignment_id": str(assignment.id),
                        "type": "new_assignment",
                        "service_name": service_name,
                        "estimated_earnings": estimated_earnings,
                    },
                )
                if success:
                    sent_count += 1
                    logger.info(
                        {
                            "event_type": "notification",
                            "event_name": "push_sent_success",
                            "device_id": str(device.id),
                        }
                    )
                else:
                    failed_count += 1
                    logger.warning(
                        {
                            "event_type": "notification",
                            "event_name": "push_sent_failed",
                            "device_id": str(device.id),
                        }
                    )

    logger.info(
        {
            "event_type": "notification",
            "event_name": "providers_notified_complete",
            "booking_id": str(booking_id),
            "push_sent_count": sent_count,
            "push_failed_count": failed_count,
        }
    )
    return {"success": True, "sent_count": sent_count, "failed_count": failed_count}


@shared_task
def notify_awaiting_bookings() -> Dict[str, Any]:
    """
    Periodic task to notify providers about pending assignments.
    Runs every minute via Celery Beat.
    """
    from app.booking_models import AssignmentQueueDB, BookingDB

    logger.info(
        {"event_type": "task_execution", "event_name": "notify_awaiting_bookings_start"}
    )

    notified_count = 0

    with Session(engine) as session:
        # Find bookings that are awaiting provider with pending assignments
        bookings = session.exec(
            select(BookingDB).where(
                BookingDB.status == "awaiting_provider", BookingDB.provider_id.is_(None)
            )
        ).all()
        
        for booking in bookings:
            # Check if there are pending assignments
            pending_assignments = session.exec(
                select(AssignmentQueueDB).where(
                    AssignmentQueueDB.booking_id == booking.id,
                    AssignmentQueueDB.status == "pending",
                )
            ).all()

            if pending_assignments:
                # Trigger notification for this booking
                notify_providers.delay(str(booking.id))
                notified_count += 1
                logger.info(
                    {
                        "event_type": "task_execution",
                        "event_name": "notify_awaiting_triggered",
                        "booking_id": str(booking.id),
                        "pending_assignments": len(pending_assignments),
                    }
                )

    logger.info(
        {
            "event_type": "task_execution",
            "event_name": "notify_awaiting_bookings_complete",
            "notified_count": notified_count,
        }
    )

    return {"success": True, "notified_count": notified_count}


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
                AssignmentQueueDB.expires_at < now,
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
    logger.info(
        {
            "event_type": "task_execution",
            "event_name": "process_unassigned_bookings_start",
        }
    )

    triggered_count = 0

    with Session(engine) as session:
        # Find bookings that need a provider but have no pending assignments
        # This acts as a retry mechanism and ensures no booking is left behind
        bookings = session.exec(
            select(BookingDB).where(
                BookingDB.status.in_(["awaiting_provider", "pending"]),
                BookingDB.provider_id.is_(None),
            )
        ).all()

        for booking in bookings:
            # Check if any pending assignments exist for this booking
            pending = session.exec(
                select(AssignmentQueueDB).where(
                    AssignmentQueueDB.booking_id == booking.id,
                    AssignmentQueueDB.status == "pending",
                )
            ).first()

            # If no pending assignments, trigger the assignment process
            if not pending:
                logger.info(
                    {
                        "event_type": "assignment_lifecycle",
                        "event_name": "retriggering_assignment",
                        "booking_id": str(booking.id),
                    }
                )
                process_new_booking.delay(str(booking.id))
                triggered_count += 1

    logger.info(
        {
            "event_type": "task_execution",
            "event_name": "process_unassigned_bookings_completed",
            "triggered_count": triggered_count,
        }
    )

    return {"success": True, "triggered_count": triggered_count}


def check_bookings_needing_reassignment(session: Session) -> None:
    """
    Check for bookings where all assignments expired and update their status.
    """
    # Find bookings in awaiting_provider status with no pending assignments
    bookings = session.exec(
        select(BookingDB).where(
            BookingDB.status == "awaiting_provider", BookingDB.provider_id.is_(None)
        )
    ).all()

    for booking in bookings:
        # Check if any pending assignments remain
        pending = session.exec(
            select(AssignmentQueueDB).where(
                AssignmentQueueDB.booking_id == booking.id,
                AssignmentQueueDB.status == "pending",
            )
        ).first()

        if not pending:
            booking.provider_distance = "Searching for more providers..."
            session.add(booking)
            logger.info(
                {
                    "event_type": "assignment_lifecycle",
                    "event_name": "requeuing_booking",
                    "booking_id": str(booking.id),
                    "reason": "all_assignments_expired",
                }
            )

    session.commit()


import math


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km using Haversine formula"""
    R = 6371  # Earth radius in km

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(
        math.radians(lat1)
    ) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def find_matching_providers(
    session: Session, booking: BookingDB
) -> list[dict[str, Any]]:
    """
    Find and score providers for a booking.
    Returns list of {provider_id, score} sorted by score descending.
    """
    logger.info(
        {
            "event_type": "provider_matching",
            "event_name": "find_matching_providers_start",
            "booking_id": str(booking.id),
            "service_id": str(booking.service_id) if booking.service_id else None,
            "booking_location": booking.location,
            "booking_lat": booking.latitude,
            "booking_lng": booking.longitude,
        }
    )

    # Get providers who offer this service
    provider_services = session.exec(
        select(ProviderServicesDB).where(
            ProviderServicesDB.service_id == booking.service_id
        )
    ).all()

    service_provider_ids = {ps.provider_id for ps in provider_services}

    logger.info(
        {
            "event_type": "provider_matching",
            "event_name": "service_providers_found",
            "booking_id": str(booking.id),
            "provider_ids_for_service": [str(pid) for pid in service_provider_ids],
        }
    )

    # Get active providers
    # If no providers offer this service, we will fallback to ALL active providers
    query = select(ProviderDB).where(ProviderDB.is_available == True)

    if service_provider_ids:
        query = query.where(ProviderDB.id.in_(service_provider_ids))

    providers = session.exec(query).all()

    logger.info(
        {
            "event_type": "provider_matching",
            "event_name": "available_providers_queried",
            "booking_id": str(booking.id),
            "available_providers_count": len(providers),
            "provider_details": [
                {
                    "id": str(p.id),
                    "business_name": p.business_name,
                    "is_available": p.is_available,
                    "lat": p.latitude,
                    "lng": p.longitude,
                }
                for p in providers
            ],
        }
    )

    # Fallback: If no providers found with service filter, assume flexibility and get ALL available
    if not providers and service_provider_ids:
        logger.info(
            {
                "event_type": "provider_matching",
                "event_name": "fallback_to_all_providers",
                "booking_id": str(booking.id),
            }
        )
        query = select(ProviderDB).where(ProviderDB.is_available == True)
        providers = session.exec(query).all()

    scored_providers = []
    MAX_DISTANCE_KM = 20.0

    for provider in providers:
        distance = None

        # Calculate distance if coordinates available
        if (
            booking.latitude
            and booking.longitude
            and provider.latitude
            and provider.longitude
        ):
            distance = calculate_distance(
                booking.latitude,
                booking.longitude,
                provider.latitude,
                provider.longitude,
            )

        # If booking requires location matching but provider has no location, skip
        elif booking.latitude and (not provider.latitude or not provider.longitude):
            distance = 0.0

        score = calculate_provider_score(session, provider, booking, distance)
        scored_providers.append(
            {"provider_id": provider.id, "score": score, "distance": distance}
        )

    # Sort by score descending
    scored_providers.sort(key=lambda x: x["score"], reverse=True)

    logger.info(
        {
            "event_type": "provider_matching",
            "event_name": "find_matching_providers_complete",
            "booking_id": str(booking.id),
            "total_matched": len(scored_providers),
            "top_3": [
                {
                    "provider_id": str(p["provider_id"]),
                    "score": p["score"],
                    "distance": p.get("distance"),
                }
                for p in scored_providers[:3]
            ],
        }
    )

    return scored_providers


def calculate_provider_score(
    session: Session,
    provider: ProviderDB,
    booking: BookingDB,
    distance: float | None = None,
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

    # Pincode matching bonus (+10 if same pincode)
    if booking.pincode and provider.pincode:
        if booking.pincode == provider.pincode:
            score += 10.0

    # Workload penalty - fewer active bookings is better
    active_bookings = session.exec(
        select(BookingDB).where(
            BookingDB.provider_id == provider.id,
            BookingDB.status.in_(["pending", "confirmed", "in_progress"]),
        )
    ).all()

    workload_penalty = min(len(active_bookings) * 2, 15)
    score -= workload_penalty

    # Experience bonus
    if provider.experience_years:
        score += min(provider.experience_years, 10)

    return max(score, 0)
