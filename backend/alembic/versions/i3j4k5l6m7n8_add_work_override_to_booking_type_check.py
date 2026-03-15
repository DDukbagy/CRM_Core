"""add WORK_OVERRIDE to chk_booking_type check constraint

Revision ID: i3j4k5l6m7n8
Revises: h2i3j4k5l6m7
Create Date: 2026-03-13 02:00:00.000000

변경 내용:
- bookings.chk_booking_type CHECK 제약에 'WORK_OVERRIDE' 추가
  (기존: LESSON | HOLIDAY → 변경: LESSON | HOLIDAY | WORK_OVERRIDE)

롤백 가능: YES (WORK_OVERRIDE 행이 없을 때)
데이터 손실: 없음
API 계약 영향: 없음
"""
from __future__ import annotations

from alembic import op

revision = "i3j4k5l6m7n8"
down_revision = "h2i3j4k5l6m7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS chk_booking_type")
    op.execute(
        "ALTER TABLE bookings ADD CONSTRAINT chk_booking_type "
        "CHECK (type = ANY (ARRAY['LESSON'::bookingtype, 'HOLIDAY'::bookingtype, 'WORK_OVERRIDE'::bookingtype]))"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS chk_booking_type")
    op.execute(
        "ALTER TABLE bookings ADD CONSTRAINT chk_booking_type "
        "CHECK (type = ANY (ARRAY['LESSON'::bookingtype, 'HOLIDAY'::bookingtype]))"
    )
