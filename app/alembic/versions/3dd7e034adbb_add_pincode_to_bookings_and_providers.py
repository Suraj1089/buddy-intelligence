"""add_pincode_to_bookings_and_providers

Revision ID: 3dd7e034adbb
Revises: ab12cd34ef56
Create Date: 2026-01-03 23:31:55.357899

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = '3dd7e034adbb'
down_revision = 'ab12cd34ef56'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('bookings', sa.Column('pincode', sa.String(), nullable=True))
    op.add_column('providers', sa.Column('pincode', sa.String(), nullable=True))


def downgrade():
    op.drop_column('providers', 'pincode')
    op.drop_column('bookings', 'pincode')
