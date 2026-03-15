"""add post_comments table

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-03-11

"""
from alembic import op
import sqlalchemy as sa

revision = 'b3c4d5e6f7a8'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS post_comments (
            id SERIAL NOT NULL,
            post_id UUID NOT NULL,
            user_id UUID NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY (post_id) REFERENCES instructor_posts (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_post_comments_post_id ON post_comments (post_id)"
    ))


def downgrade() -> None:
    op.drop_index('ix_post_comments_post_id', 'post_comments')
    op.drop_table('post_comments')
