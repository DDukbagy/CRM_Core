"""keep payment records when a customer is deleted (payments.customer_id ON DELETE RESTRICT)

Revision ID: s3t4u5v6w7x8
Revises: r2s3t4u5v6w7
Create Date: 2026-10-01 00:00:00.000000

배경:
- payments.customer_id 가 ON DELETE CASCADE 라서 회원을 지우면 결제 기록이 함께 삭제됐다.
- 대금결제 기록은 5년 보존 의무가 있다 (전자상거래법 시행령 제6조, 국세기본법 제85조의3).
  사용자 결정(2026-10-01): 일정 기간은 결제 기록이 남아 있게 한다.

변경 내용:
- payments.customer_id → users(id) 를 ON DELETE RESTRICT 로 (결제가 남아 있는 회원은 DB 에서 삭제 불가)
- 보존 기간 판단(5년)과 기간이 끝난 결제 정리는 앱(UserRepository.delete → PaymentRepository)이 한다

데이터: 행은 바꾸지 않는다
downgrade: ON DELETE CASCADE 로 되돌린다 (보존 의무를 다시 깨므로 운영에서는 쓰지 않는다)
"""
from alembic import op

revision = "s3t4u5v6w7x8"
down_revision = "r2s3t4u5v6w7"
branch_labels = None
depends_on = None


def _replace_fk(ondelete: str) -> None:
    op.execute(f"""
    DO $$
    DECLARE
        r record;
    BEGIN
        FOR r IN
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
            WHERE c.conrelid = 'public.payments'::regclass AND c.contype = 'f'
              AND array_length(c.conkey, 1) = 1 AND a.attname = 'customer_id'
        LOOP
            EXECUTE format('ALTER TABLE public.payments DROP CONSTRAINT %I', r.conname);
        END LOOP;
        ALTER TABLE public.payments
            ADD CONSTRAINT payments_customer_id_fkey FOREIGN KEY (customer_id)
            REFERENCES public.users (id) ON DELETE {ondelete};
    END $$;
    """)


def upgrade() -> None:
    _replace_fk("RESTRICT")


def downgrade() -> None:
    _replace_fk("CASCADE")
