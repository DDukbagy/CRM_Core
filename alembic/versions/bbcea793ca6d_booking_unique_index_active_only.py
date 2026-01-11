"""booking unique index active only

Revision ID: bbcea793ca6d
Revises: 9594d6202a67
Create Date: 2025-12-28 10:39:47.428854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bbcea793ca6d'
down_revision: Union[str, Sequence[str], None] = '9594d6202a67'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # (중요) 이름이 뭐든 간에 ("when", time_slot_id) 유니크 제약을 찾아서 전부 제거
    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
          -- ✅ bookings 테이블이 없으면 아무 것도 하지 않고 종료 (CI 빈 DB 대응)
          IF to_regclass('public.bookings') IS NULL THEN
            RETURN;
          END IF;

          FOR r IN
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = 'bookings'
              AND c.contype = 'u'
              AND (
                pg_get_constraintdef(c.oid) LIKE '%("when", time_slot_id)%'
                OR pg_get_constraintdef(c.oid) LIKE '%(when, time_slot_id)%'
              )
          LOOP
            EXECUTE format('ALTER TABLE public.bookings DROP CONSTRAINT IF EXISTS %I', r.conname);
          END LOOP;
        END $$;
        """
    )

    op.execute(
      """
      DO $$
      BEGIN
        IF to_regclass('public.bookings') IS NOT NULL THEN
          CREATE UNIQUE INDEX IF NOT EXISTS uq_booking_active_slot_date
          ON public.bookings ("when", time_slot_id)
          WHERE status <> 'CANCELLED';
        END IF;
      END
      $$;
      """
    )


def downgrade() -> None:
    # index 제거 (없어도 스킵)
    op.execute("DROP INDEX IF EXISTS public.uq_booking_active_slot_date;")

    # 원복: 전체 유니크 제약 다시 추가 (이미 있으면 스킵)
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = 'public'
              AND t.relname = 'bookings'
              AND c.contype = 'u'
              AND c.conname = 'uq_booking_slot_date'
          ) THEN
            ALTER TABLE public.bookings
              ADD CONSTRAINT uq_booking_slot_date UNIQUE ("when", time_slot_id);
          END IF;
        END $$;
        """
    )
