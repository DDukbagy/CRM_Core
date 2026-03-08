"""add instructor profile fields (location, specialties, bio)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-08 01:00:00.000000

변경 내용:
- users.instructor_location  : 지역 (서울/경기/인천 등)
- users.instructor_specialties: 레슨 스타일 (콤마 구분 문자열)
- users.instructor_bio        : 강사 소개글
  롤백 가능: YES / 데이터 손실: 없음 / API 영향: 없음 (신규 컬럼)
"""
from typing import Sequence, Union
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS instructor_location   VARCHAR(50)  DEFAULT NULL")
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS instructor_specialties VARCHAR(255) DEFAULT NULL")
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS instructor_bio         TEXT         DEFAULT NULL")


def downgrade() -> None:
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS instructor_bio")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS instructor_specialties")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS instructor_location")
