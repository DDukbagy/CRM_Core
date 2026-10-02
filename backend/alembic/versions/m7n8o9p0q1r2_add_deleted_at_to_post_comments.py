"""add deleted_at to post_comments (soft delete)

Revision ID: m7n8o9p0q1r2
Revises: l6m7n8o9p0q1
Create Date: 2026-10-01 00:00:00.000000

변경 내용:
- post_comments.deleted_at (TIMESTAMPTZ, NULL 허용) 추가
  - 댓글을 지우면 행은 남기고 deleted_at 기록 + 원문 비움 → 목록에 "삭제된 댓글입니다"로 표시
  - 행을 남기므로 대댓글이 함께 지워지지 않는다

데이터: 기존 행은 deleted_at = NULL (변경 없음), 데이터 손실 없음
downgrade: 컬럼 제거. 그 전에 삭제 처리된 댓글의 내용을 "삭제된 댓글입니다"로 채워
           예전 코드에서도 빈 댓글이 아니라 같은 문구로 보이게 한다 (행·대댓글은 유지)
"""
from alembic import op

revision = "m7n8o9p0q1r2"
down_revision = "l6m7n8o9p0q1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # init 마이그레이션이 현재 모델로 create_all 하므로 빈 DB에는 이미 있을 수 있다
    op.execute("ALTER TABLE public.post_comments ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL")


def downgrade() -> None:
    op.execute(
        "UPDATE public.post_comments SET content = '삭제된 댓글입니다' WHERE deleted_at IS NOT NULL"
    )
    op.execute("ALTER TABLE public.post_comments DROP COLUMN IF EXISTS deleted_at")
