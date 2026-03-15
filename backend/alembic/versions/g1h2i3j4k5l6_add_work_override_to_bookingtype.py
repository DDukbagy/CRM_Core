"""add WORK_OVERRIDE to bookingtype enum

Revision ID: g1h2i3j4k5l6
Revises: a9b0c1d2e3f4, b1c2d3e4f5a6
Create Date: 2026-03-13 00:00:00.000000

변경 내용:
- PostgreSQL bookingtype ENUM에 'WORK_OVERRIDE' 값 추가
  (정기 휴무일/휴일에 특정 슬롯만 영업일로 전환하는 타입)

롤백 가능: NO (PostgreSQL은 ENUM 값 제거 미지원, recreate 필요)
데이터 손실: 없음
API 계약 영향: 없음 (신규 타입 추가)
"""
from __future__ import annotations

from alembic import op

revision = "g1h2i3j4k5l6"
down_revision = ("a9b0c1d2e3f4", "b1c2d3e4f5a6")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE bookingtype ADD VALUE IF NOT EXISTS 'WORK_OVERRIDE'")


def downgrade() -> None:
    # PostgreSQL does not support removing values from an existing ENUM type.
    # To downgrade, recreate the enum and cast — only safe if no WORK_OVERRIDE rows exist.
    pass
