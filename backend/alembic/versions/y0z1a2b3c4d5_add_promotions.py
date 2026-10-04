"""add promotions (instructor discount/event, prototype)

강사가 웹에서 관리하는 할인·이벤트 프로모션. 고객 앱 수강권 탭에 안내로 표시 (결제 연동 전이라 실제 할인 미적용).
새 테이블만 추가. downgrade 는 테이블 삭제.

Revision ID: y0z1a2b3c4d5
Revises: x9y0z1a2b3c4
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "y0z1a2b3c4d5"
down_revision: Union[str, None] = "x9y0z1a2b3c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "promotions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pass_type_id", sa.Integer(), sa.ForeignKey("lesson_pass_types.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("discount_type", sa.String(10), nullable=False, server_default="NONE"),
        sa.Column("discount_value", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("discount_type IN ('PERCENT', 'AMOUNT', 'NONE')", name="ck_promotions_discount_type"),
        sa.CheckConstraint("end_date >= start_date", name="ck_promotions_period"),
    )
    op.create_index("ix_promotions_instructor_id", "promotions", ["instructor_id"])
    # 다른 public 테이블과 같이 RLS 켬 (정책 없음 = anon 차단, 백엔드는 소유자라 영향 없음)
    op.execute("ALTER TABLE public.promotions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index("ix_promotions_instructor_id", table_name="promotions")
    op.drop_table("promotions")
