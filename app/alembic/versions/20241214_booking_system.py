"""add booking system tables

Revision ID: 20241214_booking_system
Revises: 1a31ce608336
Create Date: 2024-12-14

Creates all tables needed for the booking system:
- profiles: User profiles
- service_categories: Categories of services
- services: Available services
- providers: Service providers
- bookings: Customer bookings
- booking_assignments: Provider assignments to bookings
- provider_services: Services offered by each provider
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers
revision: str = '20241214_booking_system'
down_revision: str = '1a31ce608336'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Profiles table
    op.create_table(
        'profiles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('full_name', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('address', sa.Text, nullable=True),
        sa.Column('avatar_url', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Service Categories table
    op.create_table(
        'service_categories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('icon', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Services table
    op.create_table(
        'services',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('base_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('duration_minutes', sa.Integer, nullable=True),
        sa.Column('category_id', UUID(as_uuid=True), sa.ForeignKey('service_categories.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Providers table
    op.create_table(
        'providers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False),
        sa.Column('business_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        sa.Column('address', sa.Text, nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('rating', sa.Numeric(3, 2), server_default='0'),
        sa.Column('experience_years', sa.Integer, server_default='0'),
        sa.Column('is_available', sa.Boolean, server_default='true'),
        sa.Column('avatar_url', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Bookings table
    op.create_table(
        'bookings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('booking_number', sa.String(50), nullable=False, unique=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('user.id'), nullable=False),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id'), nullable=True),
        sa.Column('provider_id', UUID(as_uuid=True), sa.ForeignKey('providers.id'), nullable=True),
        sa.Column('service_date', sa.Date, nullable=False),
        sa.Column('service_time', sa.String(20), nullable=False),
        sa.Column('location', sa.Text, nullable=False),
        sa.Column('special_instructions', sa.Text, nullable=True),
        sa.Column('status', sa.String(50), server_default='awaiting_provider'),
        sa.Column('estimated_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('final_price', sa.Numeric(10, 2), nullable=True),
        sa.Column('provider_distance', sa.String(50), nullable=True),
        sa.Column('estimated_arrival', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Booking Assignments table
    op.create_table(
        'booking_assignments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('booking_id', UUID(as_uuid=True), sa.ForeignKey('bookings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('provider_id', UUID(as_uuid=True), sa.ForeignKey('providers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(50), server_default='pending'),
        sa.Column('score', sa.Numeric(5, 2), nullable=True),
        sa.Column('notified_at', sa.DateTime, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('responded_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Provider Services table (many-to-many)
    op.create_table(
        'provider_services',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('provider_id', UUID(as_uuid=True), sa.ForeignKey('providers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('service_id', UUID(as_uuid=True), sa.ForeignKey('services.id', ondelete='CASCADE'), nullable=False),
        sa.Column('is_active', sa.Boolean, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('provider_services')
    op.drop_table('booking_assignments')
    op.drop_table('bookings')
    op.drop_table('providers')
    op.drop_table('services')
    op.drop_table('service_categories')
    op.drop_table('profiles')
