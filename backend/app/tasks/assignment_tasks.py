"""
Assignment background tasks for auto-assigning providers to bookings.
"""
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from celery import shared_task
from sqlmodel import Session, select

from app.core.db import engine
from app.booking_models import BookingDB, ProviderDB, AssignmentQueueDB, ProviderServicesDB


@shared_task(bind=True, max_retries=3)
def process_new_booking(self, booking_id: str) -> Dict[str, Any]:
    """
    Process a new booking and find matching providers.
    Triggered when a booking is created.
    """
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
                return {"success": True, "message": "Booking already assigned"}
            
            # Find matching providers
            providers = find_matching_providers(session, booking)
            
            if not providers:
                booking.status = "pending"
                booking.provider_distance = "No providers available"
                session.add(booking)
                session.commit()
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
        # Retry on failure
        raise self.retry(exc=e, countdown=5)


@shared_task
def notify_providers(booking_id: str) -> Dict[str, Any]:
    """
    Send notifications to providers about a new booking assignment.
    In a real app, this would integrate with push notifications, SMS, etc.
    """
    # For now, just log the notification
    # Could integrate with Firebase Cloud Messaging, Twilio, etc.
    return {"success": True, "message": f"Notified providers for booking {booking_id}"}


@shared_task
def check_expired_assignments() -> Dict[str, Any]:
    """
    Periodic task to check and expire old assignments.
    Runs every minute via Celery Beat.
    """
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


def find_matching_providers(session: Session, booking: BookingDB) -> List[Dict[str, Any]]:
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
    
    if not service_provider_ids:
        return []
    
    # Get active providers
    providers = session.exec(
        select(ProviderDB).where(
            ProviderDB.id.in_(service_provider_ids),
            ProviderDB.is_available == True
        )
    ).all()
    
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
            
            # Filter matches too far away
            if distance > MAX_DISTANCE_KM:
                continue
                
        # If booking requires location matching but provider has no location, skip
        elif booking.latitude and (not provider.latitude or not provider.longitude):
            continue
            
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
    distance: Optional[float] = None
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
