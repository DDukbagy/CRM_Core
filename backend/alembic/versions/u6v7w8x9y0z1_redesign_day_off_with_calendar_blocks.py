"""store day-off exceptions in calendar_blocks (CLOSE/OPEN) instead of bookings; default calendars

Revision ID: u6v7w8x9y0z1
Revises: t4u5v6w7x8y9
Create Date: 2026-10-01 00:00:00.000000

배경 (사용자가 정한 휴무 기능, 2026-10-01):
- 모든 강사 캘린더는 기본으로 매일 07:00~20:00, 1시간 단위 슬롯이 열려 있다
- 정기 휴무일(users.recurring_off_days) / 임시 휴무일(정기 휴무일이 아닌 날 하루 전체 닫기)
- 정기 휴무일 중 특정 날짜 열기 / 특정 날짜의 특정 시간대만 닫기
예전에는 임시 휴무일(HOLIDAY)과 정기 휴무일 열기(WORK_OVERRIDE)를 bookings 에 가짜 예약 행으로 저장해,
그 슬롯을 지우면 휴무도 사라지고 예약 코드 곳곳이 이 행들을 걸러야 했다.

변경 내용:
1. calendar_blocks.kind (CLOSE / OPEN, 기본 CLOSE) 추가
2. 취소되지 않은 HOLIDAY 예약 → CLOSE 하루 전체 블록, WORK_OVERRIDE 예약 → OPEN 시간 블록으로 옮김
3. bookings 의 HOLIDAY·WORK_OVERRIDE 행 삭제(취소된 것 포함), 그 종류용 유니크 인덱스 2개 삭제,
   chk_booking_type 을 LESSON 만 허용으로
4. 꺼져 있던 슬롯(is_active = false)을 다시 켬 (예전 "시간 휴무" 결함으로 전역에서 꺼진 것, 사용자 결정)
5. 캘린더가 없는 승인된 강사에게 캘린더 생성, 슬롯이 없는 캘린더에 기본 슬롯 13개(07~20시) 생성

downgrade: 블록을 예전 예약 행으로 되돌리고(HOLIDAY 는 그 캘린더의 첫 슬롯에 연결), kind 컬럼·제약을 복원한다.
           4·5(슬롯 재활성화, 기본 캘린더·슬롯 생성)는 되돌리지 않는다
"""
from alembic import op

revision = "u6v7w8x9y0z1"
down_revision = "t4u5v6w7x8y9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 블록 종류
    op.execute("ALTER TABLE public.calendar_blocks ADD COLUMN IF NOT EXISTS kind VARCHAR(10) NOT NULL DEFAULT 'CLOSE'")
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'ck_calendar_blocks_kind') THEN
            ALTER TABLE public.calendar_blocks ADD CONSTRAINT ck_calendar_blocks_kind CHECK (kind IN ('CLOSE', 'OPEN'));
        END IF;
    END $$;
    """)

    # 2. 예약 행 → 블록
    op.execute("""
        INSERT INTO public.calendar_blocks (calendar_id, start_date, end_date, time_slot_id, kind, reason, created_at, updated_at)
        SELECT DISTINCT ON (ts.calendar_id, b."when") ts.calendar_id, b."when", b."when", NULL, 'CLOSE', b.topic, b.created_at, now()
        FROM public.bookings b JOIN public.time_slots ts ON ts.id = b.time_slot_id
        WHERE b.type = 'HOLIDAY' AND b.status <> 'CANCELLED'
        ORDER BY ts.calendar_id, b."when", b.created_at
    """)
    op.execute("""
        INSERT INTO public.calendar_blocks (calendar_id, start_date, end_date, time_slot_id, kind, reason, created_at, updated_at)
        SELECT DISTINCT ON (ts.calendar_id, b."when", b.time_slot_id) ts.calendar_id, b."when", b."when", b.time_slot_id, 'OPEN', b.topic, b.created_at, now()
        FROM public.bookings b JOIN public.time_slots ts ON ts.id = b.time_slot_id
        WHERE b.type = 'WORK_OVERRIDE' AND b.status <> 'CANCELLED'
        ORDER BY ts.calendar_id, b."when", b.time_slot_id, b.created_at
    """)

    # 3. 예약은 레슨만
    op.execute("DELETE FROM public.bookings WHERE type IN ('HOLIDAY', 'WORK_OVERRIDE')")
    op.execute("DROP INDEX IF EXISTS public.uq_booking_holiday_slot_date")
    op.execute("DROP INDEX IF EXISTS public.uq_booking_work_override_slot_date")
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS chk_booking_type")
    op.execute("ALTER TABLE public.bookings ADD CONSTRAINT chk_booking_type CHECK (type = 'LESSON')")

    # 4. 전역으로 꺼진 슬롯 다시 켜기
    op.execute("UPDATE public.time_slots SET is_active = true, updated_at = now() WHERE is_active = false")

    # 5. 기본 캘린더·슬롯
    op.execute("""
        INSERT INTO public.calendars (topics, description, host_id, created_at, updated_at)
        SELECT '[]'::jsonb, '', u.id, now(), now()
        FROM public.users u
        WHERE u.role = 'INSTRUCTOR' AND u.status = 'ACTIVE'
          AND NOT EXISTS (SELECT 1 FROM public.calendars c WHERE c.host_id = u.id)
    """)
    op.execute("""
        INSERT INTO public.time_slots (start_time, end_time, weekdays, is_active, calendar_id, created_at, updated_at)
        SELECT make_time(h, 0, 0), make_time(h + 1, 0, 0), '[0,1,2,3,4,5,6]'::jsonb, true, c.id, now(), now()
        FROM public.calendars c CROSS JOIN generate_series(7, 19) AS h
        WHERE NOT EXISTS (SELECT 1 FROM public.time_slots t WHERE t.calendar_id = c.id)
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS chk_booking_type")
    op.execute("ALTER TABLE public.bookings ADD CONSTRAINT chk_booking_type CHECK (type IN ('LESSON','HOLIDAY','WORK_OVERRIDE'))")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_holiday_slot_date ON public.bookings ("when", time_slot_id)
        WHERE status <> 'CANCELLED' AND type = 'HOLIDAY'
    """)
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_work_override_slot_date ON public.bookings ("when", time_slot_id)
        WHERE status <> 'CANCELLED' AND type = 'WORK_OVERRIDE'
    """)
    # 하루 전체 CLOSE → HOLIDAY (첫 슬롯에 연결)
    op.execute("""
        INSERT INTO public.bookings ("when", topic, type, status, time_slot_id, guest_id, created_at, updated_at)
        SELECT b.start_date, COALESCE(b.reason, '휴무'), 'HOLIDAY', 'CONFIRMED',
               (SELECT min(t.id) FROM public.time_slots t WHERE t.calendar_id = b.calendar_id), c.host_id, b.created_at, now()
        FROM public.calendar_blocks b JOIN public.calendars c ON c.id = b.calendar_id
        WHERE b.kind = 'CLOSE' AND b.time_slot_id IS NULL
          AND EXISTS (SELECT 1 FROM public.time_slots t WHERE t.calendar_id = b.calendar_id)
    """)
    # OPEN → WORK_OVERRIDE (하루 전체 OPEN 은 그날 요일의 활성 슬롯마다)
    op.execute("""
        INSERT INTO public.bookings ("when", topic, type, status, time_slot_id, guest_id, created_at, updated_at)
        SELECT b.start_date, COALESCE(b.reason, '영업일전환'), 'WORK_OVERRIDE', 'CONFIRMED', t.id, c.host_id, b.created_at, now()
        FROM public.calendar_blocks b
        JOIN public.calendars c ON c.id = b.calendar_id
        JOIN public.time_slots t ON t.calendar_id = b.calendar_id
             AND (t.id = b.time_slot_id OR (b.time_slot_id IS NULL AND t.is_active))
        WHERE b.kind = 'OPEN'
    """)
    op.execute("DELETE FROM public.calendar_blocks WHERE kind = 'OPEN' OR (kind = 'CLOSE' AND time_slot_id IS NULL)")
    op.execute("ALTER TABLE public.calendar_blocks DROP CONSTRAINT IF EXISTS ck_calendar_blocks_kind")
    op.execute("ALTER TABLE public.calendar_blocks DROP COLUMN IF EXISTS kind")
