"""
SQLModel and Pydantic models for the booking system.
These models map to the existing Supabase database tables.
"""
import uuid
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel

# ============== ENUMS ==============

class BookingStatus(str, Enum):
    """Booking status enum matching database."""
    AWAITING_PROVIDER = "awaiting_provider"
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AssignmentStatus(str, Enum):
    """Assignment queue status enum."""
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


# ============== DATABASE MODELS (SQLModel) ==============

class ServiceCategoryDB(SQLModel, table=True):
    """Service category database model."""
    __tablename__ = "service_categories"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    name: str = SQLField(max_length=255)
    description: str | None = None
    icon: str | None = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


class ServiceDB(SQLModel, table=True):
    """Service database model."""
    __tablename__ = "services"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    name: str = SQLField(max_length=255)
    description: str | None = None
    base_price: float = SQLField(default=0)
    duration_minutes: int | None = None
    category_id: uuid.UUID | None = SQLField(foreign_key="service_categories.id")
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


class ProviderDB(SQLModel, table=True):
    """Provider database model."""
    __tablename__ = "providers"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = SQLField(unique=True)
    business_name: str = SQLField(max_length=255)
    description: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    rating: float | None = None
    experience_years: int | None = None
    is_available: bool = SQLField(default=True)
    latitude: float | None = None
    longitude: float | None = None
    avatar_url: str | None = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class ProfileDB(SQLModel, table=True):
    """User profile database model."""
    __tablename__ = "profiles"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = SQLField(unique=True)
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class BookingDB(SQLModel, table=True):
    """Booking database model."""
    __tablename__ = "bookings"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    booking_number: str = SQLField(max_length=50)
    user_id: uuid.UUID
    service_id: uuid.UUID | None = SQLField(foreign_key="services.id")
    provider_id: uuid.UUID | None = SQLField(foreign_key="providers.id")
    service_date: date  # Stored as date in DB
    service_time: str   # Keep as string for now if it's VARCHAR in DB
    location: str
    latitude: float | None = None
    longitude: float | None = None
    special_instructions: str | None = None
    status: str | None = SQLField(default="pending")
    estimated_price: float | None = None
    final_price: float | None = None
    provider_distance: str | None = None
    estimated_arrival: str | None = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class AssignmentQueueDB(SQLModel, table=True):
    """Assignment queue database model."""
    __tablename__ = "assignment_queue"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    booking_id: uuid.UUID = SQLField(foreign_key="bookings.id")
    provider_id: uuid.UUID = SQLField(foreign_key="providers.id")
    status: str = SQLField(default="pending")
    score: float | None = None
    notified_at: datetime | None = None
    responded_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


class ProviderServicesDB(SQLModel, table=True):
    """Provider-Service relationship."""
    __tablename__ = "provider_services"

    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    provider_id: uuid.UUID | None = SQLField(foreign_key="providers.id")
    service_id: uuid.UUID | None = SQLField(foreign_key="services.id")
    custom_price: float | None = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


# ============== API SCHEMAS (Pydantic) ==============

# --- Service Category Schemas ---
class ServiceCategoryBase(BaseModel):
    """Base service category schema."""
    name: str
    description: str | None = None
    icon: str | None = None


class ServiceCategoryCreate(ServiceCategoryBase):
    """Schema for creating a service category."""
    pass


class ServiceCategoryPublic(ServiceCategoryBase):
    """Schema for public service category response."""
    id: uuid.UUID

    class Config:
        from_attributes = True


class ServiceCategoriesPublic(BaseModel):
    """Schema for list of service categories."""
    data: list[ServiceCategoryPublic]
    count: int


# --- Service Schemas ---
class ServiceBase(BaseModel):
    """Base service schema."""
    name: str
    description: str | None = None
    base_price: float = 0
    duration_minutes: int | None = None
    category_id: uuid.UUID | None = None


class ServiceCreate(ServiceBase):
    """Schema for creating a service."""
    pass


class ServicePublic(ServiceBase):
    """Schema for public service response."""
    id: uuid.UUID

    class Config:
        from_attributes = True


class ServicesPublic(BaseModel):
    """Schema for list of services."""
    data: list[ServicePublic]
    count: int


# --- Provider Schemas ---
class ProviderBase(BaseModel):
    """Base provider schema."""
    business_name: str
    description: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    rating: float | None = None
    experience_years: int | None = None
    is_available: bool = True


class ProviderCreate(ProviderBase):
    """Schema for creating a provider."""
    user_id: uuid.UUID


class ProviderUpdate(BaseModel):
    """Schema for updating a provider."""
    business_name: str | None = None
    description: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    city: str | None = None
    is_available: bool | None = None


class ProviderPublic(ProviderBase):
    """Schema for public provider response."""
    id: uuid.UUID
    user_id: uuid.UUID
    avatar_url: str | None = None

    class Config:
        from_attributes = True


class ProviderServiceUpdate(BaseModel):
    """Schema for updating a provider service."""
    custom_price: float | None = None


class ProviderServicePublic(BaseModel):
    """Schema for public provider service response."""
    id: uuid.UUID
    service_id: uuid.UUID
    custom_price: float | None = None
    service: ServicePublic | None = None

    class Config:
        from_attributes = True


class ProviderServicesListPublic(BaseModel):
    """Schema for list of provider services."""
    data: list[ProviderServicePublic]
    count: int


# --- Booking Schemas ---
class BookingBase(BaseModel):
    """Base booking schema."""
    service_id: uuid.UUID
    service_date: date
    service_time: str
    location: str
    special_instructions: str | None = None


class BookingCreate(BookingBase):
    """Schema for creating a booking."""
    estimated_price: float | None = None


class BookingUpdate(BaseModel):
    """Schema for updating a booking."""
    status: BookingStatus | None = None
    final_price: float | None = None


class BookingPublic(BaseModel):
    """Schema for public booking response."""
    id: uuid.UUID
    booking_number: str
    user_id: uuid.UUID
    service_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    service_date: date
    service_time: str
    location: str
    special_instructions: str | None = None
    status: str | None = None
    estimated_price: float | None = None
    final_price: float | None = None
    provider_distance: str | None = None
    estimated_arrival: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProfilePublic(BaseModel):
    """Schema for public profile response."""
    full_name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None


class BookingWithDetails(BookingPublic):
    """Booking with related service and provider details."""
    service: ServicePublic | None = None
    provider: ProviderPublic | None = None
    user_profile: ProfilePublic | None = None


class BookingsPublic(BaseModel):
    """Schema for list of bookings."""
    data: list[BookingWithDetails]
    count: int


# --- Assignment Schemas ---
class AssignmentPublic(BaseModel):
    """Schema for public assignment response."""
    id: uuid.UUID
    booking_id: uuid.UUID
    provider_id: uuid.UUID
    status: str
    score: float | None = None
    notified_at: datetime | None = None
    expires_at: datetime | None = None

    class Config:
        from_attributes = True


class AssignmentWithBooking(AssignmentPublic):
    """Assignment with booking details."""
    booking: BookingWithDetails | None = None


class AssignmentsPublic(BaseModel):
    """Schema for list of assignments."""
    data: list[AssignmentWithBooking]
    count: int


class AssignmentResponse(BaseModel):
    """Response for accept/decline assignment."""
    success: bool
    message: str | None = None
    error: str | None = None
    booking_id: uuid.UUID | None = None


# --- Generic Response ---
class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
