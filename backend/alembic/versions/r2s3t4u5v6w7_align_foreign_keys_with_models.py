"""align foreign keys with model declarations (missing FKs, delete rules, duplicate FK)

Revision ID: r2s3t4u5v6w7
Revises: q1r2s3t4u5v6
Create Date: 2026-10-01 00:00:00.000000

배경:
- 원격 DB 와 모델 선언 비교(2026-10-01) 결과, 모델에는 있는데 원격에 없는 FK 가 있고
  time_slots 에는 같은 FK 가 두 개(삭제 규칙이 다른) 걸려 있었다.

변경 내용 — 아래 컬럼마다 기존 FK 를 모두 지우고, 모델과 같은 이름·삭제 규칙으로 하나만 다시 만든다:
- calendars.host_id         → users(id)     ON DELETE CASCADE   (원격에 없었음)
- instructor_staff.instructor_id → users(id) ON DELETE CASCADE  (원격에 없었음)
- instructor_staff.staff_user_id → users(id) ON DELETE CASCADE  (원격에 없었음)
- time_slots.calendar_id    → calendars(id) ON DELETE CASCADE   (중복 FK 하나 제거)
- calendar_blocks.calendar_id → calendars(id) ON DELETE CASCADE (삭제 규칙 없던 것을 CASCADE 로.
  강사 삭제 → 캘린더 삭제 때 블록이 막지 않도록)

데이터: 행은 바꾸지 않는다. FK 를 걸 수 없는 행(참조 대상이 없는 행)이 있으면 바로 실패한다.
       원격 확인 결과 해당 행 0건
downgrade: 원격의 이전 모양으로 되돌린다 (calendars.host_id·instructor_staff FK 제거,
           calendar_blocks FK 는 삭제 규칙 없이). 제거했던 중복 FK 는 다시 만들지 않는다
"""
from alembic import op

revision = "r2s3t4u5v6w7"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None

SPECS = [
    # (테이블, 컬럼, 참조 테이블, 삭제 규칙)
    ("calendars", "host_id", "users", "CASCADE"),
    ("instructor_staff", "instructor_id", "users", "CASCADE"),
    ("instructor_staff", "staff_user_id", "users", "CASCADE"),
    ("time_slots", "calendar_id", "calendars", "CASCADE"),
    ("calendar_blocks", "calendar_id", "calendars", "CASCADE"),
]


def _replace_fk(table: str, column: str, ref: str, ondelete: str | None) -> None:
    on_delete = f" ON DELETE {ondelete}" if ondelete else ""
    op.execute(f"""
    DO $$
    DECLARE
        r record;
    BEGIN
        FOR r IN
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
            WHERE c.conrelid = 'public.{table}'::regclass AND c.contype = 'f'
              AND array_length(c.conkey, 1) = 1 AND a.attname = '{column}'
        LOOP
            EXECUTE format('ALTER TABLE public.{table} DROP CONSTRAINT %I', r.conname);
        END LOOP;
        ALTER TABLE public.{table}
            ADD CONSTRAINT {table}_{column}_fkey FOREIGN KEY ({column}) REFERENCES public.{ref} (id){on_delete};
    END $$;
    """)


def _drop_fk(table: str, column: str) -> None:
    op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {table}_{column}_fkey")


def upgrade() -> None:
    for table, column, ref, ondelete in SPECS:
        _replace_fk(table, column, ref, ondelete)


def downgrade() -> None:
    _drop_fk("calendars", "host_id")
    _drop_fk("instructor_staff", "instructor_id")
    _drop_fk("instructor_staff", "staff_user_id")
    _replace_fk("calendar_blocks", "calendar_id", "calendars", None)
