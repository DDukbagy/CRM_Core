"""create post_media table for posts domain

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-03-12

변경 내용:
- post_media 테이블 신규 생성 (posts 도메인 PostMedia 모델용)
  (d5e6f7a8b9c0에서 post_media → instructor_post_media 로 rename 됐으므로
   posts 도메인의 PostMedia 가 사용할 별도 테이블을 재생성)

롤백 가능: YES
데이터 손실: 없음 (신규 테이블)
API 계약 영향: 없음
"""
from alembic import op
import sqlalchemy as sa

revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.post_media (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            post_id         UUID NOT NULL REFERENCES public.posts(id) ON DELETE CASCADE,
            media_type      VARCHAR(10) NOT NULL DEFAULT 'IMAGE',
            url             TEXT NOT NULL,
            s3_key_source   TEXT NOT NULL,
            sort_order      INTEGER NOT NULL DEFAULT 0,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_post_media_post_id ON public.post_media (post_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS public.post_media")
