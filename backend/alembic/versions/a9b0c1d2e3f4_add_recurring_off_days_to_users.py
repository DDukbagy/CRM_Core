"""add recurring_off_days to users

Revision ID: a9b0c1d2e3f4
Revises: f8a9b0c1d2e3
Create Date: 2026-03-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'a9b0c1d2e3f4'
down_revision = 'f8a9b0c1d2e3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS recurring_off_days JSONB DEFAULT '[]'::jsonb"
    ))


def downgrade() -> None:
    op.drop_column('users', 'recurring_off_days')
