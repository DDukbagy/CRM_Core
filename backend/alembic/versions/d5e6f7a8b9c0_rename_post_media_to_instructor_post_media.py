"""rename post_media to instructor_post_media

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-12

변경 내용:
- post_media 테이블을 instructor_post_media로 rename
  (posts 도메인의 PostMedia 클래스와 __tablename__ 충돌 해소)
"""
from alembic import op

revision = 'd5e6f7a8b9c0'
down_revision = 'c4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.rename_table('post_media', 'instructor_post_media')


def downgrade() -> None:
    op.rename_table('instructor_post_media', 'post_media')
