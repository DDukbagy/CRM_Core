"""users: 로그인한 사용자가 자기 행만 읽는 RLS 정책

웹(src/proxy.ts)은 로그인 후 Supabase 로 public.users 의 자기 role 을 직접 읽는다.
users 는 RLS 가 켜져 있어 SELECT 정책이 없으면 아무 행도 안 보이고 웹 로그인이 ROLE_UNAVAILABLE 로 막힌다.
개발 DB 에는 이 정책이 대시보드에서 수동으로 만들어져 있었고 마이그레이션에는 없어서, 새 DB(데모·운영)에서 빠졌다.

- Supabase 가 아닌 DB(로컬 테스트 Postgres)에는 authenticated 역할·auth.uid() 가 없으므로 건너뛴다
- users 에 SELECT 정책이 이미 있으면(개발 DB 의 수동 정책) 건드리지 않는다
- 백엔드는 테이블 소유자로 접속해 RLS 를 우회하므로 영향 없음
downgrade: 이 마이그레이션이 만든 정책만 지운다

Revision ID: z1a2b3c4d5e6
Revises: y0z1a2b3c4d5
"""
from typing import Sequence, Union

from alembic import op

revision: str = "z1a2b3c4d5e6"
down_revision: Union[str, None] = "y0z1a2b3c4d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

POLICY = "users read own row"


def upgrade() -> None:
    op.execute(f"""
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
           AND EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                       WHERE n.nspname = 'auth' AND p.proname = 'uid')
           AND NOT EXISTS (SELECT 1 FROM pg_policies
                           WHERE schemaname = 'public' AND tablename = 'users' AND cmd IN ('SELECT', 'ALL'))
        THEN
            EXECUTE 'CREATE POLICY "{POLICY}" ON public.users FOR SELECT TO authenticated USING (auth.uid() = id)';
        END IF;
    END $$;
    """)


def downgrade() -> None:
    op.execute(f'DROP POLICY IF EXISTS "{POLICY}" ON public.users')
