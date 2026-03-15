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
    # e6f7a8b9c0d1에서 이미 생성된 경우 건너뜀
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='instructor_posts' AND column_name='media_type'"
    ))
    if result.fetchone() is None:
        op.add_column('instructor_posts', sa.Column('media_type', sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column('instructor_posts', 'media_type')
