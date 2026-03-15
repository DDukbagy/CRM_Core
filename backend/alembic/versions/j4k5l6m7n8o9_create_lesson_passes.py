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
    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS lesson_pass_types (
            id SERIAL NOT NULL,
            instructor_id UUID NOT NULL,
            name VARCHAR(100) NOT NULL,
            duration_hours SMALLINT NOT NULL,
            session_count SMALLINT NOT NULL,
            price INTEGER,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            CONSTRAINT fk_lpt_instructor FOREIGN KEY (instructor_id) REFERENCES users(id)
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_lesson_pass_types_instructor ON lesson_pass_types (instructor_id)"
    ))

    op.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS customer_passes (
            id SERIAL NOT NULL,
            pass_type_id INTEGER NOT NULL,
            customer_id UUID NOT NULL,
            instructor_id UUID NOT NULL,
            pass_name VARCHAR(100) NOT NULL,
            duration_hours SMALLINT NOT NULL,
            sessions_total SMALLINT NOT NULL,
            sessions_used SMALLINT NOT NULL DEFAULT 0,
            price_paid INTEGER,
            status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
            note TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id),
            CONSTRAINT fk_cp_pass_type FOREIGN KEY (pass_type_id) REFERENCES lesson_pass_types(id),
            CONSTRAINT fk_cp_customer FOREIGN KEY (customer_id) REFERENCES users(id),
            CONSTRAINT fk_cp_instructor FOREIGN KEY (instructor_id) REFERENCES users(id)
        )
    """))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_customer_passes_customer ON customer_passes (customer_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_customer_passes_instructor ON customer_passes (instructor_id)"
    ))
    op.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_customer_passes_status ON customer_passes (status)"
    ))


def downgrade() -> None:
    op.drop_index("ix_customer_passes_status", table_name="customer_passes")
    op.drop_index("ix_customer_passes_instructor", table_name="customer_passes")
    op.drop_index("ix_customer_passes_customer", table_name="customer_passes")
    op.drop_table("customer_passes")
    op.drop_index("ix_lesson_pass_types_instructor", table_name="lesson_pass_types")
    op.drop_table("lesson_pass_types")
