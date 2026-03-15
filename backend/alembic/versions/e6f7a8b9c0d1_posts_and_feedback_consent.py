"""posts table and users.feedback_consent

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-03-09 10:00:00.000000

변경 내용:
- users.feedback_consent 컬럼 추가 (고객 피드백 공개 동의)
- instructor_posts 테이블 생성 (강사 게시물: PROMOTION | FEEDBACK)

롤백 가능: YES
데이터 손실: 없음
API 계약 영향: 없음 (신규)
"""
from typing import Sequence, Union
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.users ADD COLUMN IF NOT EXISTS feedback_consent BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.instructor_posts (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            instructor_id   UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
            type            VARCHAR(20) NOT NULL CHECK (type IN ('PROMOTION','FEEDBACK')),
            title           VARCHAR(200),
            content         TEXT,
            media_url       TEXT,
            customer_id     UUID REFERENCES public.users(id) ON DELETE SET NULL,
            is_public       BOOLEAN NOT NULL DEFAULT FALSE,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_instructor_posts_instructor_id ON public.instructor_posts(instructor_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_instructor_posts_customer_id ON public.instructor_posts(customer_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_instructor_posts_is_public ON public.instructor_posts(is_public)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.instructor_posts")
    op.execute("ALTER TABLE public.users DROP COLUMN IF EXISTS feedback_consent")
