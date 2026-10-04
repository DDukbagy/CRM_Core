"""merge memberships into customer passes (payments.customer_pass_id, drop memberships)

멤버십(횟수제·기간제 회원권)과 수강권이 같은 역할이라 수강권 하나로 합친다 (사용자 결정 2026-10-04).
- payments.customer_pass_id 추가 (→ customer_passes.id ON DELETE SET NULL). payments.membership_id 제거
- bookings.membership_id 제거 (레슨 완료 시 차감은 이미 수강권이 담당)
- memberships 테이블 삭제. 멤버십 행이 하나라도 있으면 데이터 손실을 막기 위해 중단한다

downgrade: 테이블·컬럼 구조를 되살린다 (지운 데이터는 없으므로 복원할 데이터도 없음)

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
"""
from typing import Sequence, Union

from alembic import op

revision: str = "w8x9y0z1a2b3"
down_revision: Union[str, None] = "v7w8x9y0z1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF to_regclass('public.memberships') IS NOT NULL
             AND EXISTS (SELECT 1 FROM public.memberships) THEN
            RAISE EXCEPTION 'memberships 에 데이터가 있어 중단합니다. 수강권으로 옮긴 뒤 다시 실행하세요.';
          END IF;
        END $$;
        """
    )
    # 빈 DB 에서는 init(create_all)이 현재 모델로 컬럼을 이미 만든다 → IF NOT EXISTS
    op.execute("ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS customer_pass_id INTEGER")
    op.execute("ALTER TABLE public.payments DROP CONSTRAINT IF EXISTS payments_customer_pass_id_fkey")
    op.execute(
        "ALTER TABLE public.payments ADD CONSTRAINT payments_customer_pass_id_fkey "
        "FOREIGN KEY (customer_pass_id) REFERENCES public.customer_passes(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE public.payments DROP COLUMN IF EXISTS membership_id")
    op.execute("ALTER TABLE public.bookings DROP COLUMN IF EXISTS membership_id")
    op.execute("DROP TABLE IF EXISTS public.memberships")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS public.memberships (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
            instructor_id UUID NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
            type VARCHAR(10) NOT NULL,
            total_count SMALLINT,
            remaining_count SMALLINT,
            started_at DATE,
            expires_at DATE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT chk_membership_type CHECK (type IN ('TIMES', 'PERIOD'))
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_memberships_customer_id ON public.memberships(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memberships_instructor_id ON public.memberships(instructor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_memberships_is_active ON public.memberships(is_active)")
    op.execute("ALTER TABLE public.memberships ENABLE ROW LEVEL SECURITY")
    op.execute(
        "ALTER TABLE public.payments ADD COLUMN IF NOT EXISTS membership_id UUID "
        "REFERENCES public.memberships(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_membership_id ON public.payments(membership_id)")
    op.execute(
        "ALTER TABLE public.bookings ADD COLUMN IF NOT EXISTS membership_id UUID "
        "REFERENCES public.memberships(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE public.payments DROP CONSTRAINT IF EXISTS payments_customer_pass_id_fkey")
    op.execute("ALTER TABLE public.payments DROP COLUMN IF EXISTS customer_pass_id")
