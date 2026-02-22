"""time_slots weekdays default all days

Revision ID: 5cc9b860b849
Revises: 41fd85a02af6
Create Date: 2026-02-21 04:46:46.082493

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '5cc9b860b849'
down_revision: Union[str, Sequence[str], None] = '91d68413f8d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_WEEKDAYS_JSONB = "'[0,1,2,3,4,5,6]'::jsonb"

def upgrade() -> None:
    """Upgrade schema."""
    # 컬럼 없으면 추가
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema='public'
              AND table_name='time_slots'
              AND column_name='weekdays'
          ) THEN
            ALTER TABLE public.time_slots
              ADD COLUMN weekdays jsonb;
          END IF;
        END $$;
        """
    )

    # 기존 NULL 채우기
    op.execute(f"UPDATE public.time_slots SET weekdays={DEFAULT_WEEKDAYS_JSONB} WHERE weekdays IS NULL")

    # default를 jsonb로 + not null
    op.alter_column(
        "time_slots",
        "weekdays",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=False,
        server_default=sa.text(DEFAULT_WEEKDAYS_JSONB),
    )

def downgrade() -> None:
    """Downgrade schema."""
    # nullable 풀고 default 제거
    op.alter_column(
        "time_slots",
        "weekdays",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        nullable=True,
        server_default=None,
    )
