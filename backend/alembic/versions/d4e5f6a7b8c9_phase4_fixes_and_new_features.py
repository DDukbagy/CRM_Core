"""Phase 4: instructor_staff, FK indexes, CHECK constraints, lesson_notes, consultation

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-08 03:00:00.000000

변경 내용:
- instructor_staff 테이블 생성 (CRITICAL: 없으면 스태프 API 크래시)
- 누락 인덱스 추가 (bookings.guest_id, bookings.time_slot_id, time_slots.calendar_id)
- CHECK 제약 추가 (bookings.status, memberships.type, match_requests.status, users.status, instructor_tier)
- instructor_match_requests.request_type 컬럼 추가 (MATCH | CONSULTATION)
- 활성 매칭 partial unique index를 request_type 단위로 교체
- lesson_notes 테이블 생성

롤백 가능: YES (제약/인덱스 DROP, 테이블 DROP)
데이터 손실: 없음
API 계약 영향: instructor_match_requests에 request_type 추가(신규 컬럼, 기존 데이터 MATCH 기본값)
"""
from typing import Sequence, Union
from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def _add_check_if_not_exists(constraint_name: str, table: str, check_expr: str) -> None:
    """PostgreSQL CHECK 제약을 안전하게 추가 (이미 존재하면 스킵)."""
    op.execute(f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = '{constraint_name}'
            ) THEN
                ALTER TABLE {table}
                ADD CONSTRAINT {constraint_name} CHECK ({check_expr});
            END IF;
        END $$;
    """)


def upgrade() -> None:
    # ────────────────────────────────────────────────────────────
    # 1. instructor_staff 테이블 (CRITICAL: 없으면 런타임 크래시)
    # ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.instructor_staff (
            instructor_id   UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            staff_user_id   UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (instructor_id, staff_user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_instructor_staff_instructor_id ON public.instructor_staff(instructor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_instructor_staff_staff_user_id ON public.instructor_staff(staff_user_id)")

    # ────────────────────────────────────────────────────────────
    # 2. 누락 FK 인덱스 (CRITICAL: Full Table Scan 방지)
    # ────────────────────────────────────────────────────────────
    op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_guest_id ON public.bookings(guest_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_time_slot_id ON public.bookings(time_slot_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_time_slots_calendar_id ON public.time_slots(calendar_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_status ON public.bookings(status)")
    op.execute('CREATE INDEX IF NOT EXISTS ix_bookings_when ON public.bookings("when")')

    # ────────────────────────────────────────────────────────────
    # 3. CHECK 제약 (HIGH: 잘못된 값이 DB에 들어가는 것 방지)
    # ────────────────────────────────────────────────────────────
    _add_check_if_not_exists(
        "chk_booking_status", "public.bookings",
        "status IN ('REQUESTED','CONFIRMED','CANCELLED','COMPLETED','NO_SHOW')",
    )
    _add_check_if_not_exists(
        "chk_membership_type", "public.memberships",
        "type IN ('TIMES','PERIOD')",
    )
    _add_check_if_not_exists(
        "chk_match_request_status", "public.instructor_match_requests",
        "status IN ('PENDING','ACCEPTED','REJECTED','CANCELLED')",
    )
    _add_check_if_not_exists(
        "chk_user_status", "public.users",
        "status IN ('ACTIVE','PENDING','SUSPENDED')",
    )
    _add_check_if_not_exists(
        "chk_instructor_tier", "public.users",
        "instructor_tier IS NULL OR instructor_tier IN ('NORMAL','NAMED')",
    )
    _add_check_if_not_exists(
        "chk_booking_type", "public.bookings",
        "type IN ('LESSON','HOLIDAY')",
    )

    # ────────────────────────────────────────────────────────────
    # 4. instructor_match_requests.request_type 추가 (상담/매칭 분리)
    # ────────────────────────────────────────────────────────────
    op.execute("""
        ALTER TABLE public.instructor_match_requests
        ADD COLUMN IF NOT EXISTS request_type VARCHAR(20) NOT NULL DEFAULT 'MATCH'
    """)
    _add_check_if_not_exists(
        "chk_match_request_type", "public.instructor_match_requests",
        "request_type IN ('MATCH','CONSULTATION')",
    )

    # 기존 partial unique (request_type 구분 없이) → request_type 단위로 교체
    # 고객당 MATCH 1개 + CONSULTATION 1개 동시에 가능
    op.execute("DROP INDEX IF EXISTS public.uq_match_request_active_customer")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_match_request_active_per_type
        ON public.instructor_match_requests(customer_id, request_type)
        WHERE status IN ('PENDING','ACCEPTED')
    """)

    # ────────────────────────────────────────────────────────────
    # 5. lesson_notes 테이블 (강사 레슨 노트)
    # ────────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.lesson_notes (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            booking_id      INTEGER NOT NULL REFERENCES public.bookings(id) ON DELETE CASCADE,
            instructor_id   UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            content         TEXT NOT NULL,
            is_shared       BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE(booking_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_lesson_notes_booking_id ON public.lesson_notes(booking_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_lesson_notes_instructor_id ON public.lesson_notes(instructor_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.lesson_notes")

    op.execute("DROP INDEX IF EXISTS public.uq_match_request_active_per_type")
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_match_request_active_customer
        ON public.instructor_match_requests(customer_id)
        WHERE status IN ('PENDING','ACCEPTED')
    """)
    op.execute("ALTER TABLE public.instructor_match_requests DROP COLUMN IF EXISTS request_type")

    # CHECK 제약 제거
    for name in [
        "chk_booking_status", "chk_membership_type", "chk_match_request_status",
        "chk_user_status", "chk_instructor_tier", "chk_booking_type",
        "chk_match_request_type",
    ]:
        op.execute(f"ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS {name}")
        op.execute(f"ALTER TABLE public.memberships DROP CONSTRAINT IF EXISTS {name}")
        op.execute(f"ALTER TABLE public.instructor_match_requests DROP CONSTRAINT IF EXISTS {name}")
        op.execute(f"ALTER TABLE public.users DROP CONSTRAINT IF EXISTS {name}")

    # 인덱스 제거
    for idx in [
        "ix_bookings_guest_id", "ix_bookings_time_slot_id", "ix_time_slots_calendar_id",
        "ix_bookings_status", "ix_bookings_when",
        "ix_instructor_staff_instructor_id", "ix_instructor_staff_staff_user_id",
    ]:
        op.execute(f"DROP INDEX IF EXISTS public.{idx}")

    op.execute("DROP TABLE IF EXISTS public.instructor_staff")
