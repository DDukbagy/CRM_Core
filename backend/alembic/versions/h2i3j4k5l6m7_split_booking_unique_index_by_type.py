"""split booking unique index by type (LESSON/HOLIDAY/WORK_OVERRIDE)

Revision ID: h2i3j4k5l6m7
Revises: g1h2i3j4k5l6
Create Date: 2026-03-13 01:00:00.000000

변경 내용:
- 기존 uq_booking_active_slot_date (type 구분 없이 unique) 제거
- 타입별 부분 인덱스로 분리:
  - LESSON: 같은 슬롯+날짜에 중복 불가
  - HOLIDAY: 같은 슬롯+날짜에 중복 불가
  - WORK_OVERRIDE: 같은 슬롯+날짜에 중복 불가
  → HOLIDAY + WORK_OVERRIDE 는 같은 슬롯+날짜에 공존 가능

롤백 가능: YES
데이터 손실: 없음
API 계약 영향: 없음
"""
from __future__ import annotations

from alembic import op

revision = "h2i3j4k5l6m7"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 통합 unique index 제거
    op.execute("DROP INDEX IF EXISTS uq_booking_active_slot_date")

    # 타입별 partial unique index 생성
    op.execute("""
        CREATE UNIQUE INDEX uq_booking_lesson_slot_date
        ON bookings(\"when\", time_slot_id)
        WHERE status <> 'CANCELLED' AND type = 'LESSON'
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_booking_holiday_slot_date
        ON bookings(\"when\", time_slot_id)
        WHERE status <> 'CANCELLED' AND type = 'HOLIDAY'
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_booking_work_override_slot_date
        ON bookings(\"when\", time_slot_id)
        WHERE status <> 'CANCELLED' AND type = 'WORK_OVERRIDE'
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_booking_lesson_slot_date")
    op.execute("DROP INDEX IF EXISTS uq_booking_holiday_slot_date")
    op.execute("DROP INDEX IF EXISTS uq_booking_work_override_slot_date")

    op.execute("""
        CREATE UNIQUE INDEX uq_booking_active_slot_date
        ON bookings(\"when\", time_slot_id)
        WHERE status <> 'CANCELLED'
    """)
