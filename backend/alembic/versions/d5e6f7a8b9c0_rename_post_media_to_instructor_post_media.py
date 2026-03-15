"""rename post_media to instructor_post_media

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-12

변경 내용:
- post_media 테이블을 instructor_post_media로 rename
  (posts 도메인의 PostMedia 클래스와 __tablename__ 충돌 해소)
"""
from alembic import op
import sqlalchemy as sa

revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # instructor_post_media already exists (created in e6f7a8b9c0d1).
    # If post_media exists too, drop it; otherwise rename it.
    op.execute(sa.text("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = 'post_media'
            ) THEN
                IF EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'instructor_post_media'
                ) THEN
                    DROP TABLE post_media;
                ELSE
                    ALTER TABLE post_media RENAME TO instructor_post_media;
                END IF;
            END IF;
        END $$;
    """))


def downgrade() -> None:
    op.rename_table('instructor_post_media', 'post_media')
