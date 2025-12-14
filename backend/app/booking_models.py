"""
SQLModel and Pydantic models for the booking system.
These models map to the existing Supabase database tables.
"""
import uuid
from datetime import datetime, date, time
from enum import Enum
from typing import Optional, List

from pydantic import BaseModel, Field
from sqlmodel import SQLModel, Field as SQLField, Relationship


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
    description: Optional[str] = None
    icon: Optional[str] = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


class ServiceDB(SQLModel, table=True):
    """Service database model."""
    __tablename__ = "services"
    
    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    name: str = SQLField(max_length=255)
    description: Optional[str] = None
    base_price: float = SQLField(default=0)
    duration_minutes: Optional[int] = None
    category_id: Optional[uuid.UUID] = SQLField(foreign_key="service_categories.id")
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


class ProviderDB(SQLModel, table=True):
    """Provider database model."""
    __tablename__ = "providers"
    
    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = SQLField(unique=True)
    business_name: str = SQLField(max_length=255)
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    rating: Optional[float] = None
    experience_years: Optional[int] = None
    is_available: bool = SQLField(default=True)
    avatar_url: Optional[str] = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class ProfileDB(SQLModel, table=True):
    """User profile database model."""
    __tablename__ = "profiles"
    
    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = SQLField(unique=True)
    full_name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class BookingDB(SQLModel, table=True):
    """Booking database model."""
    __tablename__ = "bookings"
    
    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    booking_number: str = SQLField(max_length=50)
    user_id: uuid.UUID
    service_id: Optional[uuid.UUID] = SQLField(foreign_key="services.id")
    provider_id: Optional[uuid.UUID] = SQLField(foreign_key="providers.id")
    service_date: str  # Stored as string in DB
    service_time: str
    location: str
    special_instructions: Optional[str] = None
    status: Optional[str] = SQLField(default="pending")
    estimated_price: Optional[float] = None
    final_price: Optional[float] = None
    provider_distance: Optional[str] = None
    estimated_arrival: Optional[str] = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class AssignmentQueueDB(SQLModel, table=True):
    """Assignment queue database model."""
    __tablename__ = "assignment_queue"
    
    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    booking_id: uuid.UUID = SQLField(foreign_key="bookings.id")
    provider_id: uuid.UUID = SQLField(foreign_key="providers.id")
    status: str = SQLField(default="pending")
    score: Optional[float] = None
    notified_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


class ProviderServicesDB(SQLModel, table=True):
    """Provider-Service relationship."""
    __tablename__ = "provider_services"
    
    id: uuid.UUID = SQLField(default_factory=uuid.uuid4, primary_key=True)
    provider_id: Optional[uuid.UUID] = SQLField(foreign_key="providers.id")
    service_id: Optional[uuid.UUID] = SQLField(foreign_key="services.id")
    custom_price: Optional[float] = None
    created_at: datetime = SQLField(default_factory=datetime.utcnow)


# ============== API SCHEMAS (Pydantic) ==============

# --- Service Category Schemas ---
class ServiceCategoryBase(BaseModel):
    """Base service category schema."""
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None


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
    data: List[ServiceCategoryPublic]
    count: int


# --- Service Schemas ---
class ServiceBase(BaseModel):
    """Base service schema."""
    name: str
    description: Optional[str] = None
    base_price: float = 0
    duration_minutes: Optional[int] = None
    category_id: Optional[uuid.UUID] = None


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
    data: List[ServicePublic]
    count: int


# --- Provider Schemas ---
class ProviderBase(BaseModel):
    """Base provider schema."""
    business_name: str
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    rating: Optional[float] = None
    experience_years: Optional[int] = None
    is_available: bool = True


class ProviderCreate(ProviderBase):
    """Schema for creating a provider."""
    user_id: uuid.UUID


class ProviderUpdate(BaseModel):
    """Schema for updating a provider."""
    business_name: Optional[str] = None
    description: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    is_available: Optional[bool] = None


class ProviderPublic(ProviderBase):
    """Schema for public provider response."""
    id: uuid.UUID
    user_id: uuid.UUID
    avatar_url: Optional[str] = None
    
    class Config:
        from_attributes = True


# --- Booking Schemas ---
class BookingBase(BaseModel):
    """Base booking schema."""
    service_id: uuid.UUID
    service_date: str
    service_time: str
    location: str
    special_instructions: Optional[str] = None


class BookingCreate(BookingBase):
    """Schema for creating a booking."""
    estimated_price: Optional[float] = None


class BookingUpdate(BaseModel):
    """Schema for updating a booking."""
    status: Optional[BookingStatus] = None
    final_price: Optional[float] = None


class BookingPublic(BaseModel):
    """Schema for public booking response."""
    id: uuid.UUID
    booking_number: str
    user_id: uuid.UUID
    service_id: Optional[uuid.UUID] = None
    provider_id: Optional[uuid.UUID] = None
    service_date: str
    service_time: str
    location: str
    special_instructions: Optional[str] = None
    status: Optional[str] = None
    estimated_price: Optional[float] = None
    final_price: Optional[float] = None
    provider_distance: Optional[str] = None
    estimated_arrival: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BookingWithDetails(BookingPublic):
    """Booking with related service and provider details."""
    service: Optional[ServicePublic] = None
    provider: Optional[ProviderPublic] = None


class BookingsPublic(BaseModel):
    """Schema for list of bookings."""
    data: List[BookingWithDetails]
    count: int


# --- Assignment Schemas ---
class AssignmentPublic(BaseModel):
    """Schema for public assignment response."""
    id: uuid.UUID
    booking_id: uuid.UUID
    provider_id: uuid.UUID
    status: str
    score: Optional[float] = None
    notified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class AssignmentWithBooking(AssignmentPublic):
    """Assignment with booking details."""
    booking: Optional[BookingWithDetails] = None


class AssignmentsPublic(BaseModel):
    """Schema for list of assignments."""
    data: List[AssignmentWithBooking]
    count: int


class AssignmentResponse(BaseModel):
    """Response for accept/decline assignment."""
    success: bool
    message: Optional[str] = None
    error: Optional[str] = None
    booking_id: Optional[uuid.UUID] = None


# --- Generic Response ---
class MessageResponse(BaseModel):
    """Generic message response."""
    message: str
