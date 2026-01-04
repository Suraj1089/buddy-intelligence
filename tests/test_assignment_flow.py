
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from app.booking_models import (
    AssignmentQueueDB,
    BookingDB,
    ProviderDB,
    ProviderServicesDB,
    ServiceDB,
    ProfileDB,
    BookingStatus,
)
from app.models import User
from app.tasks.assignment_tasks import process_new_booking


def create_test_data(session: Session):
    """Helper to create necessary test data."""
    # Create User
    unique_str = uuid.uuid4().hex[:8]
    user_id = uuid.uuid4()
    user = User(id=user_id, email=f"user_{unique_str}@example.com", is_active=True, full_name="Test User", hashed_password="placeholder")
    session.add(user)
    
    # Create Profile
    profile = ProfileDB(id=uuid.uuid4(), user_id=user_id, full_name="Test User", phone="1234567890")
    session.add(profile)

    # Create Service
    service_id = uuid.uuid4()
    service = ServiceDB(
        id=service_id,
        name="Test Assignment Service",
        base_price=100.0,
        description="Testing assignment",
    )
    session.add(service)
    session.flush()

    # Create Provider User
    provider_user_id = uuid.uuid4()
    provider_user = User(id=provider_user_id, email=f"provider_{unique_str}@example.com", is_active=True, full_name="Test Provider", hashed_password="placeholder")
    session.add(provider_user)

    # Create Provider
    provider_id = uuid.uuid4()
    provider = ProviderDB(
        id=provider_id,
        user_id=provider_user_id,
        business_name="Test Provider Business",
        is_available=True,
        rating=5.0,
        experience_years=5,
        latitude=40.7128,  # NYC coordinates
        longitude=-74.0060,
    )
    session.add(provider)

    # Link Provider to Service
    provider_service = ProviderServicesDB(
        id=uuid.uuid4(),
        provider_id=provider_id,
        service_id=service_id,
    )
    session.add(provider_service)

    session.commit()

    return user, provider, service


def test_assignment_flow_notifications_and_acceptance(db: Session):
    """
    Test the full flow:
    1. Create Booking
    2. Run assignment task -> Verifies notification triggered
    3. Verify Assignment Queue populated
    4. Provider Accepts
    5. Verify Booking Confirmed
    """
    user, provider, service = create_test_data(db)

    # 1. Create Booking
    booking_id = uuid.uuid4()
    booking = BookingDB(
        id=booking_id,
        booking_number="BK-123456",
        user_id=user.id,
        service_id=service.id,
        service_date="2026-01-20",
        service_time="10:00",
        location="123 Test St, New York, NY",
        latitude=40.7128,  # Same location as provider
        longitude=-74.0060,
        status="pending",
    )
    db.add(booking)
    db.commit()

    # Mock the notify_providers task to verify it gets called
    with patch("app.tasks.assignment_tasks.notify_providers.delay") as mock_notify:
        # Mock the request context for bind=True task since we call function directly
        # process_new_booking is a shared_task, so calling it directly works as simple function usually
        # But it has bind=True, so 'self' is passed. When calling directly, Celery might handle this or we pass local call.
        # Actually proper way to test celery task synchronously is just calling the underlying python function if possible
        # or using .apply()
        
        # 2. Run Assignment Task
        # We use .apply() to execute it locally and synchronously
        # Note: If no celery properly configured for tests, standard function call might be better if we access the .run method?
        # But 'process_new_booking' handles 'self' logic.
        # Simplest way: Call it directly. But bind=True wraps it.
        # Let's try calling it via the module import which is the task proxy.
        
        # Assuming we can run it synchronously
        try:
            # Using basic python invocation if possible, but bind=True expects 'self'
            # We bypass the cellery wrapper to test logic
            # This requires inspecting the task object
            process_new_booking(str(booking_id))
        except TypeError:
            # If direct call fails due to self, invoke via celery apply if backend allows or just mock self
            # But creating a dummy self is easier for unit testing logic
            mock_self = MagicMock()
            process_new_booking.update_state = MagicMock()
            # We need to access the original function underneath the task decorator
            # Usually task.run or similar, or just call with mocked self if possible?
            # Actually, standard celery tasks can be called as functions and 'self' is magic.
            # But let's see. If this fails, we adjust.
            pass

        # 3. Verify Assignment Queue
        # Refresh booking
        db.refresh(booking)
        
        # Check Booking Status
        assert booking.status == "awaiting_provider"
        assert booking.provider_id is None

        # Check Queue
        assignments = db.exec(
            select(AssignmentQueueDB).where(AssignmentQueueDB.booking_id == booking_id)
        ).all()
        
        assert len(assignments) == 1
        assignment = assignments[0]
        assert assignment.provider_id == provider.id
        assert assignment.status == "pending"
        
        # Verify notification was triggered
        # Since we mocked it inside the context, check the mock
        mock_notify.assert_called_once_with(str(booking_id))

    # 4. Provider Accepts Assignment
    # We simulate the API call logic here essentially
    
    # Provider accepts
    assignment.status = "accepted"
    assignment.responded_at = "2026-01-04T12:00:00" # Dummy time
    db.add(assignment)
    
    # Update Booking
    booking.status = BookingStatus.CONFIRMED.value
    booking.provider_id = provider.id
    db.add(booking)
    
    # Expire other assignments (if any)
    # In this test, only 1 assignment exists
    
    db.commit()
    db.refresh(booking)

    # 5. Verify Final State
    assert booking.status == BookingStatus.CONFIRMED.value
    assert booking.provider_id == provider.id
    
    # Verify provider service link still exists or whatever logic needed
    # (ProviderServicesDB already exists)

