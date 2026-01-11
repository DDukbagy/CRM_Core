"""add posts post_media post_consents

Revision ID: 748ea71fe207
Revises: bbcea793ca6d
Create Date: 2026-01-11 02:27:10.194650

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '748ea71fe207'
down_revision: Union[str, Sequence[str], None] = 'bbcea793ca6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'PRIVATE'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "posts_status_check",
        "posts",
        "status in ('DRAFT','PRIVATE','PENDING_CONSENT','PUBLIC','ARCHIVED')",
    )
    op.create_index("idx_posts_owner_created_at", "posts", ["owner_user_id", "created_at"])
    op.create_index("idx_posts_status_created_at", "posts", ["status", "created_at"])
    op.create_index("idx_posts_instructor_created_at", "posts", ["instructor_id", "created_at"])

    op.create_table(
        "post_media",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'CREATED'")),
        sa.Column("source_filename", sa.Text(), nullable=True),
        sa.Column("source_content_type", sa.Text(), nullable=True),
        sa.Column("source_size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("s3_key_source", sa.Text(), nullable=False, unique=True),
        sa.Column("s3_key_output", sa.Text(), nullable=True, unique=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint("post_media_type_check", "post_media", "media_type in ('VIDEO','IMAGE')")
    op.create_check_constraint(
        "post_media_status_check",
        "post_media",
        "status in ('CREATED','UPLOADED','PROCESSING','READY','FAILED')",
    )
    op.create_index("idx_post_media_post_created_at", "post_media", ["post_id", "created_at"])
    op.create_index("idx_post_media_status_created_at", "post_media", ["status", "created_at"])

    op.create_table(
        "post_consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("post_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_check_constraint(
        "post_consents_action_check",
        "post_consents",
        "action in ('GRANT_PUBLIC','REVOKE_PUBLIC')",
    )
    op.create_index("idx_post_consents_post_created_at", "post_consents", ["post_id", "created_at"])
    op.create_index("idx_post_consents_user_created_at", "post_consents", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_post_consents_user_created_at", table_name="post_consents")
    op.drop_index("idx_post_consents_post_created_at", table_name="post_consents")
    op.drop_constraint("post_consents_action_check", "post_consents", type_="check")
    op.drop_table("post_consents")

    op.drop_index("idx_post_media_status_created_at", table_name="post_media")
    op.drop_index("idx_post_media_post_created_at", table_name="post_media")
    op.drop_constraint("post_media_status_check", "post_media", type_="check")
    op.drop_constraint("post_media_type_check", "post_media", type_="check")
    op.drop_table("post_media")

    op.drop_index("idx_posts_instructor_created_at", table_name="posts")
    op.drop_index("idx_posts_status_created_at", table_name="posts")
    op.drop_index("idx_posts_owner_created_at", table_name="posts")
    op.drop_constraint("posts_status_check", "posts", type_="check")
    op.drop_table("posts")
