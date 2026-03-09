"""Phase 2: memberships, payments, user info fields, booking membership_id, match unique constraint

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-08 02:00:00.000000

변경 내용:
- users: birth_date, gender, lesson_purpose (고객), career_years, certifications (강사)
- memberships 테이블 생성 (TIMES/PERIOD 타입)
- payments 테이블 생성 (TOSS/KAKAO/NAVER/CASH/TRANSFER)
- bookings.membership_id FK 추가
- instructor_match_requests: 활성 매칭 중복 방지 partial unique index

롤백 가능: YES
데이터 손실: 없음
API 계약 영향: 없음 (신규 컬럼/테이블)
"""
from typing import Sequence, Union

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. users 테이블 — 고객/강사 추가 정보 컬럼
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS birth_date DATE DEFAULT NULL")
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS gender VARCHAR(10) DEFAULT NULL")
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS lesson_purpose TEXT DEFAULT NULL")
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS career_years SMALLINT DEFAULT NULL")
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS certifications TEXT DEFAULT NULL")

    # 2. memberships 테이블
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.memberships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            instructor_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            type VARCHAR(10) NOT NULL CHECK (type IN ('TIMES', 'PERIOD')),
            total_count SMALLINT,
            remaining_count SMALLINT,
            started_at DATE,
            expires_at DATE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_memberships_customer_id ON public.memberships(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memberships_instructor_id ON public.memberships(instructor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memberships_is_active ON public.memberships(is_active)")

    # 3. payments 테이블
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.payments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            membership_id UUID REFERENCES public.memberships(id) ON DELETE SET NULL,
            amount INTEGER NOT NULL,
            method VARCHAR(20) NOT NULL CHECK (method IN ('TOSS', 'KAKAO', 'NAVER', 'CASH', 'TRANSFER')),
            status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
                CHECK (status IN ('PENDING', 'COMPLETED', 'FAILED', 'REFUNDED')),
            pg_payment_id VARCHAR(200),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_customer_id ON public.payments(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_membership_id ON public.payments(membership_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_status ON public.payments(status)")

    # 4. bookings.membership_id FK
    op.execute("""
        ALTER TABLE public.bookings
        ADD COLUMN IF NOT EXISTS membership_id UUID
        REFERENCES public.memberships(id) ON DELETE SET NULL
    """)

    # 5. instructor_match_requests — 활성 매칭 중복 방지
    #    한 고객이 PENDING/ACCEPTED 상태 매칭을 동시에 하나 이상 가질 수 없음
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_match_request_active_customer
        ON public.instructor_match_requests(customer_id)
        WHERE status IN ('PENDING', 'ACCEPTED')
    """)


def downgrade() -> None:
    # 역순으로 제거
    op.execute("DROP INDEX IF EXISTS public.uq_match_request_active_customer")
    op.execute("ALTER TABLE public.bookings DROP COLUMN IF EXISTS membership_id")
    op.execute("DROP TABLE IF EXISTS public.payments")
    op.execute("DROP TABLE IF EXISTS public.memberships")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS certifications")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS career_years")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS lesson_purpose")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS gender")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS birth_date")
