"""keep contract records (memberships, customer passes) on user delete; users.withdrawn_at

멤버십·발급 수강권은 계약 기록(전자상거래법 시행령 제6조, 5년)이라 회원 삭제로 지워지면 안 된다.
- memberships.customer_id / instructor_id: CASCADE → RESTRICT
- customer_passes.customer_id / instructor_id: (규칙 없음 = NO ACTION) → RESTRICT
- users.withdrawn_at: 탈퇴 처리 시각. 이미 탈퇴한 회원은 updated_at 으로 채운다

보존 기간이 끝난 기록은 회원 삭제 때 앱(UserRepository.delete)이 먼저 지운다.
데이터 변경 없음(FK 규칙·컬럼 추가). downgrade 가능.

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
"""
from typing import Sequence, Union

from alembic import op

revision: str = "v7w8x9y0z1a2"
down_revision: Union[str, None] = "u6v7w8x9y0z1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    ("memberships", "customer_id"),
    ("memberships", "instructor_id"),
    ("customer_passes", "customer_id"),
    ("customer_passes", "instructor_id"),
)


def _drop_user_fk(table: str, column: str) -> None:
    """users 를 가리키는 이 컬럼의 FK 를 이름과 관계없이 제거 (환경마다 이름이 다를 수 있음)"""
    op.execute(
        f"""
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
            WHERE c.contype = 'f'
              AND c.conrelid = 'public.{table}'::regclass
              AND c.confrelid = 'public.users'::regclass
              AND a.attname = '{column}'
          LOOP
            EXECUTE format('ALTER TABLE public.{table} DROP CONSTRAINT %I', r.conname);
          END LOOP;
        END $$;
        """
    )


def _set_rule(rule: str) -> None:
    for table, column in COLUMNS:
        _drop_user_fk(table, column)
        op.create_foreign_key(f"{table}_{column}_fkey", table, "users", [column], ["id"], ondelete=rule)


def upgrade() -> None:
    _set_rule("RESTRICT")
    # 빈 DB 에서는 init 마이그레이션(create_all)이 현재 모델로 이미 만든다
    op.execute("ALTER TABLE public.users ADD COLUMN IF NOT EXISTS withdrawn_at TIMESTAMP WITH TIME ZONE")
    op.execute("UPDATE public.users SET withdrawn_at = updated_at WHERE status = 'WITHDRAWN' AND withdrawn_at IS NULL")


def downgrade() -> None:
    op.drop_column("users", "withdrawn_at")
    for table, column in COLUMNS:
        _drop_user_fk(table, column)
    for column in ("customer_id", "instructor_id"):
        op.create_foreign_key(f"memberships_{column}_fkey", "memberships", "users", [column], ["id"], ondelete="CASCADE")
        op.create_foreign_key(f"customer_passes_{column}_fkey", "customer_passes", "users", [column], ["id"])
