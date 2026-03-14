"""create lesson_pass_types and customer_passes tables

Revision ID: j4k5l6m7n8o9
Revises: i3j4k5l6m7n8
Create Date: 2026-03-14 00:00:00.000000

변경 내용:
- lesson_pass_types: 강사가 제공하는 수강권 상품 정의 테이블
- customer_passes: 고객에게 발급된 수강권 인스턴스 테이블

롤백 가능: YES (데이터 손실 없이 drop 가능)
데이터 손실: 없음 (신규 테이블)
API 계약 영향: 없음 (신규 엔드포인트 추가)
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "j4k5l6m7n8o9"
down_revision = "i3j4k5l6m7n8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lesson_pass_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("duration_hours", sa.SmallInteger(), nullable=False),
        sa.Column("session_count", sa.SmallInteger(), nullable=False),
        sa.Column("price", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"], name="fk_lpt_instructor"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lesson_pass_types_instructor", "lesson_pass_types", ["instructor_id"])

    op.create_table(
        "customer_passes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("pass_type_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("pass_name", sa.String(100), nullable=False),
        sa.Column("duration_hours", sa.SmallInteger(), nullable=False),
        sa.Column("sessions_total", sa.SmallInteger(), nullable=False),
        sa.Column("sessions_used", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("price_paid", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["pass_type_id"], ["lesson_pass_types.id"], name="fk_cp_pass_type"),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], name="fk_cp_customer"),
        sa.ForeignKeyConstraint(["instructor_id"], ["users.id"], name="fk_cp_instructor"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_passes_customer", "customer_passes", ["customer_id"])
    op.create_index("ix_customer_passes_instructor", "customer_passes", ["instructor_id"])
    op.create_index("ix_customer_passes_status", "customer_passes", ["status"])


def downgrade() -> None:
    op.drop_index("ix_customer_passes_status", table_name="customer_passes")
    op.drop_index("ix_customer_passes_instructor", table_name="customer_passes")
    op.drop_index("ix_customer_passes_customer", table_name="customer_passes")
    op.drop_table("customer_passes")
    op.drop_index("ix_lesson_pass_types_instructor", table_name="lesson_pass_types")
    op.drop_table("lesson_pass_types")
