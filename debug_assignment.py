
from sqlmodel import Session, select

from app.booking_models import (
    AssignmentQueueDB,
    BookingDB,
    ProviderDB,
    ProviderServicesDB,
    ServiceDB,
)
from app.core.db import engine


def check_assignment_status():
    with Session(engine) as session:
        # Get the most recent booking
        booking = session.exec(select(BookingDB).order_by(BookingDB.created_at.desc())).first()
        if not booking:
            print("No bookings found.")
            return

        print(f"Checking Booking: {booking.booking_number} (ID: {booking.id})")
        print(f"  Status: {booking.status}")
        print(f"  Service ID: {booking.service_id}")

        if not booking.service_id:
            print("  Booking has no service ID!")
            return

        # Check Service
        service = session.get(ServiceDB, booking.service_id)
        if service:
            print(f"  Service Name: {service.name}")
        else:
            print("  Service not found in DB!")

        # Check Providers offering this service
        provider_services = session.exec(
            select(ProviderServicesDB).where(ProviderServicesDB.service_id == booking.service_id)
        ).all()

        print(f"  Found {len(provider_services)} providers linked to this service.")

        linked_provider_ids = [ps.provider_id for ps in provider_services]

        # Check all providers
        all_providers = session.exec(select(ProviderDB)).all()
        print(f"  Total Providers in DB: {len(all_providers)}")

        for provider in all_providers:
            is_linked = provider.id in linked_provider_ids
            print(f"  Provider: {provider.business_name} (ID: {provider.id})")
            print(f"    - Is Available: {provider.is_available}")
            print(f"    - Offers Service: {is_linked}")
            if booking.location and provider.latitude:
                 # simple check
                 print(f"    - Location: {provider.latitude}, {provider.longitude}")
            else:
                 print(f"    - Location: {provider.latitude}, {provider.longitude}")

        # Check Assignment Queue
        print("\nChecking Assignment Queue for this booking:")
        assignments = session.exec(
            select(AssignmentQueueDB).where(AssignmentQueueDB.booking_id == booking.id)
        ).all()

        if not assignments:
            print("  No assignments found in queue!")
        else:
            for assignment in assignments:
                provider = session.get(ProviderDB, assignment.provider_id)
                provider_name = provider.business_name if provider else "Unknown Provider"
                print(f"  Assignment ID: {assignment.id}")
                print(f"    - Provider: {provider_name} (ID: {assignment.provider_id})")
                print(f"    - Status: {assignment.status}")
                print(f"    - Expires At: {assignment.expires_at}")
                print(f"    - Created At: {assignment.created_at}")

if __name__ == "__main__":
    check_assignment_status()
