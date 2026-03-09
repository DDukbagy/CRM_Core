"""add instructor_tier to users and instructor_match_requests table

Revision ID: a1b2c3d4e5f6
Revises: e5278775d3fc
Create Date: 2026-03-08 00:00:00.000000

변경 내용:
- users.instructor_tier 컬럼 추가 (NORMAL | NAMED, default NORMAL)
- instructor_match_requests 테이블 생성
  - 롤백 가능: YES
  - 데이터 손실: 없음
  - API 계약 영향: 없음 (신규 테이블)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e5278775d3fc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users.instructor_tier — 이미 존재하면 스킵
    op.execute("""
        ALTER TABLE public.users
        ADD COLUMN IF NOT EXISTS instructor_tier VARCHAR(10) DEFAULT 'NORMAL'
    """)

    # 2. instructor_match_requests 테이블 — 이미 존재하면 스킵
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.instructor_match_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            customer_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            instructor_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
            fee INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_instructor_match_requests_customer_id ON public.instructor_match_requests(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_instructor_match_requests_instructor_id ON public.instructor_match_requests(instructor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_instructor_match_requests_status ON public.instructor_match_requests(status)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.instructor_match_requests")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS instructor_tier")
