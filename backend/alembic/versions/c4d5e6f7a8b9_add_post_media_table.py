"""add post_media table

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'c4d5e6f7a8b9'
down_revision = 'b3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS post_media (
            id SERIAL PRIMARY KEY,
            post_id UUID NOT NULL REFERENCES instructor_posts(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            media_type VARCHAR(10) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_post_media_post_id ON post_media (post_id)"
    ))


def downgrade() -> None:
    op.drop_index('ix_post_media_post_id', 'post_media')
    op.drop_table('post_media')
