"""recreate instructor_post_media with correct schema

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-03-12

변경 내용:
- instructor_post_media 테이블을 올바른 스키마로 재생성
  (기존 테이블은 s3_key_source 등 다른 구조였음)

롤백 가능: YES (단, 기존 데이터 손실)
데이터 손실: instructor_post_media 기존 데이터 삭제됨 (로컬 개발 환경)
"""
from alembic import op
import sqlalchemy as sa

revision = 'f8a9b0c1d2e3'
down_revision = 'e7f8a9b0c1d2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS instructor_post_media CASCADE"))
    op.execute(sa.text("""
        CREATE TABLE instructor_post_media (
            id SERIAL PRIMARY KEY,
            post_id UUID NOT NULL REFERENCES instructor_posts(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            media_type VARCHAR(10) NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_instructor_post_media_post_id ON instructor_post_media (post_id)"
    ))


def downgrade() -> None:
    op.drop_table('instructor_post_media')
