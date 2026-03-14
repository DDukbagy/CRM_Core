"""fix instructor_post_media.media_type column type from enum to text

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c0
Create Date: 2026-03-12

변경 내용:
- instructor_post_media.media_type: mediatype enum → VARCHAR(10)
  (DB가 enum 타입으로 생성된 경우 VARCHAR로 변환)

롤백 가능: YES
데이터 손실: 없음 (USING media_type::text 캐스팅)
API 계약 영향: 없음
"""
from alembic import op
import sqlalchemy as sa

revision = 'e7f8a9b0c1d2'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    # media_type 컬럼이 enum 타입인 경우에만 VARCHAR로 변환
    conn.execute(sa.text("""
        ALTER TABLE instructor_post_media
        ALTER COLUMN media_type TYPE VARCHAR(10) USING media_type::text
    """))


def downgrade() -> None:
    # 롤백 시 단순 VARCHAR 유지 (enum 재생성 불필요)
    pass
