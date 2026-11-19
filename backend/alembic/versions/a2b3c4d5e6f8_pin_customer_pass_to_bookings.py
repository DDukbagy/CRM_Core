"""bookings: 예약에 수강권 고정 (customer_pass_id)

예약할 때 어떤 수강권으로 할지 고정하고, 완료·노쇼 때 그 수강권에서 차감한다 (docs/worklog/booking-pass-pinning.md).

1. bookings.customer_pass_id 추가 (customer_passes 참조, ON DELETE SET NULL) + 인덱스
2. 기존 진행 중 레슨 예약(신청·확정·취소 요청)을 채운다: 그 강사의 가장 오래된 활성 수강권, 없으면 가장 오래된 수강권
3. 그 강사의 수강권이 하나도 없는 진행 중 예약은 취소하고 사유를 남긴다 (지우지 않음)
4. CHECK 제약: 진행 중 레슨 예약은 수강권이 반드시 있다. 끝난 예약은 예전 기록이라 비워 둔다
downgrade: 제약·인덱스·칸을 지운다. 3번에서 취소한 예약은 되돌리지 않는다 (cancel_reason 으로 찾을 수 있음)

Revision ID: a2b3c4d5e6f8
Revises: z1a2b3c4d5e6
"""
from typing import Sequence, Union

from alembic import op

revision: str = "a2b3c4d5e6f8"
down_revision: Union[str, None] = "z1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ACTIVE = "('REQUESTED', 'CONFIRMED', 'CANCEL_REQUESTED')"
CLEANUP_REASON = "수강권 없음 (예약 수강권 고정 마이그레이션에서 정리)"


def upgrade() -> None:
    # 빈 DB 에서는 init 마이그레이션(create_all)이 현재 모델로 칸을 이미 만들었으므로 IF NOT EXISTS (payments.customer_pass_id 와 같은 방식)
    op.execute("ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS customer_pass_id INTEGER")
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS bookings_customer_pass_id_fkey")
    op.execute(
        "ALTER TABLE public.bookings ADD CONSTRAINT bookings_customer_pass_id_fkey "
        "FOREIGN KEY (customer_pass_id) REFERENCES public.customer_passes(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_customer_pass_id ON public.bookings (customer_pass_id)")

    # 진행 중 예약에 그 강사(캘린더 주인)의 수강권을 채운다
    op.execute(f"""
    UPDATE bookings b
    SET customer_pass_id = (
        SELECT cp.id FROM customer_passes cp
        JOIN time_slots ts ON ts.id = b.time_slot_id
        JOIN calendars c ON c.id = ts.calendar_id
        WHERE cp.customer_id = b.guest_id AND cp.instructor_id = c.host_id
        ORDER BY (cp.status = 'ACTIVE') DESC, cp.id
        LIMIT 1
    )
    WHERE b.type = 'LESSON' AND b.status IN {ACTIVE} AND b.customer_pass_id IS NULL
    """)
    # 그래도 비어 있으면 그 강사의 수강권이 없는 예약: 취소로 정리
    op.execute(f"""
    UPDATE bookings
    SET status = 'CANCELLED', cancel_reason = '{CLEANUP_REASON}'
    WHERE type = 'LESSON' AND status IN {ACTIVE} AND customer_pass_id IS NULL
    """)

    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS ck_bookings_active_lesson_has_pass")
    op.execute(
        "ALTER TABLE public.bookings ADD CONSTRAINT ck_bookings_active_lesson_has_pass "
        f"CHECK (type <> 'LESSON' OR status NOT IN {ACTIVE} OR customer_pass_id IS NOT NULL)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS ck_bookings_active_lesson_has_pass")
    op.execute("DROP INDEX IF EXISTS public.ix_bookings_customer_pass_id")
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS bookings_customer_pass_id_fkey")
    op.execute("ALTER TABLE public.bookings DROP COLUMN IF EXISTS customer_pass_id")
