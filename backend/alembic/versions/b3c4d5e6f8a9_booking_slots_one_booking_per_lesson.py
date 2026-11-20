"""bookings: 예약 1건 = 레슨 1회, 예약이 차지하는 시간은 booking_slots 로

수강권은 "회당 N시간"인데 예약은 슬롯 1개만 가질 수 있어 2시간 레슨이 예약 2건이 됐다 (docs/worklog/booking-lesson-hours.md).

1. bookings.calendar_id 추가: 예약이 속한 캘린더 (지금까지는 슬롯을 거쳐 찾았다). 기존 행은 슬롯의 캘린더로 채운 뒤 NOT NULL
2. booking_slots 신설: 예약이 차지하는 시간 한 칸씩 (예약, 슬롯, 날짜, holds_slot)
3. 기존 예약을 각자 슬롯 1개짜리 예약으로 옮긴다. 취소된 예약은 holds_slot = false (시간 기록만 남는다)
4. 유니크 인덱스 "같은 날짜·슬롯을 차지하는 예약은 하나"를 booking_slots 로 옮긴다
5. bookings.time_slot_id 와 그 인덱스(uq_booking_lesson_slot_date, ix_bookings_time_slot_id)를 지운다

downgrade: bookings.time_slot_id 를 되살리고 예약마다 가장 이른 슬롯 하나로 채운다.
여러 시간 예약은 첫 시간만 남으므로(나머지 시간 정보 손실) 운영 DB 에서는 쓰지 않는다.

Revision ID: b3c4d5e6f8a9
Revises: a2b3c4d5e6f8
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b3c4d5e6f8a9"
down_revision: Union[str, None] = "a2b3c4d5e6f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 빈 DB 에서는 init 마이그레이션(create_all)이 현재 모델로 칸·테이블을 이미 만들었으므로 IF NOT EXISTS
    # 1. 예약이 속한 캘린더
    op.execute("ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS calendar_id BIGINT")
    op.execute("""
    UPDATE public.bookings b SET calendar_id = ts.calendar_id
    FROM public.time_slots ts
    WHERE ts.id = b.time_slot_id AND b.calendar_id IS NULL
    """)
    op.execute("ALTER TABLE public.bookings ALTER COLUMN calendar_id SET NOT NULL")
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS bookings_calendar_id_fkey")
    op.execute(
        "ALTER TABLE public.bookings ADD CONSTRAINT bookings_calendar_id_fkey "
        "FOREIGN KEY (calendar_id) REFERENCES public.calendars(id) ON DELETE CASCADE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_calendar_id ON public.bookings (calendar_id)")

    # 2. 예약이 차지하는 시간
    op.execute("""
    CREATE TABLE IF NOT EXISTS public.booking_slots (
        id SERIAL PRIMARY KEY,
        booking_id INTEGER NOT NULL REFERENCES public.bookings(id) ON DELETE CASCADE,
        time_slot_id BIGINT NOT NULL REFERENCES public.time_slots(id) ON DELETE CASCADE,
        "when" DATE NOT NULL,
        holds_slot BOOLEAN NOT NULL DEFAULT true
    )
    """)
    # 다른 public 테이블과 같이 RLS 를 켠다 (정책 없음: anon 키로는 읽지 못하고, 백엔드는 테이블 소유자라 그대로 쓴다)
    op.execute("ALTER TABLE public.booking_slots ENABLE ROW LEVEL SECURITY")

    # 3. 기존 예약 → 슬롯 1개짜리 예약. 그 시간을 차지하던 조건(취소 아닌 레슨)은 옛 유니크 인덱스와 같다
    op.execute("""
    INSERT INTO public.booking_slots (booking_id, time_slot_id, "when", holds_slot)
    SELECT b.id, b.time_slot_id, b."when", (b.status <> 'CANCELLED' AND b.type = 'LESSON')
    FROM public.bookings b
    WHERE NOT EXISTS (SELECT 1 FROM public.booking_slots s WHERE s.booking_id = b.id)
    """)

    # 4. 같은 날짜·슬롯을 차지하는 예약은 하나
    op.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_slots_slot_date ON public.booking_slots ("when", time_slot_id) '
        "WHERE holds_slot"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_booking_slots_booking_id ON public.booking_slots (booking_id)")

    # 5. 옛 칸과 인덱스 (칸을 지우면 FK 도 함께 지워진다)
    op.execute("DROP INDEX IF EXISTS public.uq_booking_lesson_slot_date")
    op.execute("DROP INDEX IF EXISTS public.ix_bookings_time_slot_id")
    op.execute("ALTER TABLE public.bookings DROP COLUMN IF EXISTS time_slot_id")


def downgrade() -> None:
    op.execute("ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS time_slot_id INTEGER")
    op.execute("""
    UPDATE public.bookings b SET time_slot_id = (
        SELECT s.time_slot_id FROM public.booking_slots s
        JOIN public.time_slots ts ON ts.id = s.time_slot_id
        WHERE s.booking_id = b.id
        ORDER BY ts.start_time, s.id
        LIMIT 1
    )
    """)
    op.execute("ALTER TABLE public.bookings ALTER COLUMN time_slot_id SET NOT NULL")
    op.execute(
        "ALTER TABLE public.bookings ADD CONSTRAINT bookings_time_slot_id_fkey "
        "FOREIGN KEY (time_slot_id) REFERENCES public.time_slots(id) ON DELETE CASCADE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_time_slot_id ON public.bookings (time_slot_id)")
    op.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_lesson_slot_date ON public.bookings ("when", time_slot_id) '
        "WHERE status <> 'CANCELLED' AND type = 'LESSON'"
    )
    op.execute("DROP TABLE IF EXISTS public.booking_slots")
    op.execute("DROP INDEX IF EXISTS public.ix_bookings_calendar_id")
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS bookings_calendar_id_fkey")
    op.execute("ALTER TABLE public.bookings DROP COLUMN IF EXISTS calendar_id")
