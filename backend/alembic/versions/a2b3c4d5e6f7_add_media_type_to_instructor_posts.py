"""add media_type to instructor_posts

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('instructor_posts', sa.Column('media_type', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('instructor_posts', 'media_type')
