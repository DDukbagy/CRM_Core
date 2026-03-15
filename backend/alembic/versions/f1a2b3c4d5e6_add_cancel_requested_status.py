"""add CANCEL_REQUESTED to booking status check constraint

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-03-10 14:00:00.000000

변경 내용:
- bookings.chk_booking_status CHECK 제약에 CANCEL_REQUESTED 추가
"""
from __future__ import annotations

from alembic import op

revision = "f1a2b3c4d5e6"
down_revision = "e6f7a8b9c0d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 기존 제약 삭제 후 CANCEL_REQUESTED 포함하여 재생성
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS chk_booking_status")
    op.execute(
        "ALTER TABLE public.bookings ADD CONSTRAINT chk_booking_status "
        "CHECK (status IN ('REQUESTED','CONFIRMED','CANCEL_REQUESTED','CANCELLED','COMPLETED','NO_SHOW'))"
    )


def downgrade() -> None:
    # CANCEL_REQUESTED 행이 있으면 downgrade 불가 — 수동 처리 필요
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS chk_booking_status")
    op.execute(
        "ALTER TABLE public.bookings ADD CONSTRAINT chk_booking_status "
        "CHECK (status IN ('REQUESTED','CONFIRMED','CANCELLED','COMPLETED','NO_SHOW'))"
    )
