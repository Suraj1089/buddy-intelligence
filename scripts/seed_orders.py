
import random
import uuid
from datetime import datetime, timedelta, date

from sqlmodel import Session, select
from app.core.db import engine
from app.models import User
from app.booking_models import BookingDB, ProviderDB, ServiceDB, BookingStatus, AssignmentQueueDB

def seed_orders(provider_uuid=None):
    with Session(engine) as session:
        # Get target provider
        if provider_uuid:
            provider = session.get(ProviderDB, provider_uuid)
        else:
            # Get any available provider
            provider = session.exec(select(ProviderDB).where(ProviderDB.is_available == True)).first()
            
        if not provider:
            print("No provider found to assign orders to.")
            return

        print(f"Creating orders for provider: {provider.business_name} (ID: {provider.id})")

        # Get service categories offered by this provider (or random if none linked)
        # For simplicity, we'll pick extended random services
        services = session.exec(select(ServiceDB)).all()
        if not services:
            print("No services found in DB. Run basic seed first.")
            return

        # Create a Dummy User to be the "Customer"
        user = session.exec(select(User).where(User.email == "customer@example.com")).first()
        if not user:
            # existing or new
            user = session.exec(select(User)).first()
            
        statuses = [
            BookingStatus.PENDING, 
            BookingStatus.CONFIRMED, 
            BookingStatus.IN_PROGRESS, 
            BookingStatus.COMPLETED, 
            BookingStatus.CANCELLED
        ]

        created_assignments = []

        for i, status in enumerate(statuses):
            service = random.choice(services)
            
            # create booking
            booking_id = uuid.uuid4()
            booking = BookingDB(
                id=booking_id,
                booking_number=f"SEED-{status.value.upper()}-{random.randint(100,999)}",
                user_id=user.id,
                service_id=service.id,
                provider_id=provider.id if status != BookingStatus.PENDING else None, # Assign provider unless pending
                service_date=date.today() + timedelta(days=i),
                service_time="10:00 AM",
                location="123 Test St, San Francisco, CA",
                latitude=37.7749,
                longitude=-122.4194,
                status=status,
                estimated_price=service.base_price,
                final_price=service.base_price if status == BookingStatus.COMPLETED else None,
                provider_distance="5.2 miles" if status != BookingStatus.PENDING else None,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(booking)
            session.flush()  # Ensure booking ID exists in DB before linking assignment
            
            # For PENDING status, explicitly create an assignment queue item
            if status == BookingStatus.PENDING:
                booking.status = "awaiting_provider" # Update to awaiting
                booking.provider_id = None
                
                assignment = AssignmentQueueDB(
                    id=uuid.uuid4(),
                    booking_id=booking_id,
                    provider_id=provider.id,
                    status="pending",
                    score=95.5,
                    notified_at=datetime.utcnow(),
                    expires_at=datetime.utcnow() + timedelta(hours=24), # Long expiry so you can see it
                    created_at=datetime.utcnow()
                )
                session.add(assignment)
                created_assignments.append(assignment.id)
                print(f"  [+] Created PENDING Assignment for Booking {booking.booking_number}")

            session.commit()
            print(f"  [+] Created Booking {booking.booking_number} with status {status.value}")
            
        print(f"\nSuccessfully seeded {len(statuses)} orders for provider {provider.id}")

if __name__ == "__main__":
    import sys
    # Optional: Pass provider ID as arg
    pid = sys.argv[1] if len(sys.argv) > 1 else None
    seed_orders(pid)
