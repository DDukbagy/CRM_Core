"""add time_slot_id to calendar_blocks (date-specific slot closing)

Revision ID: n8o9p0q1r2s3
Revises: m7n8o9p0q1r2
Create Date: 2026-10-01 00:00:00.000000

배경:
- 강사 앱의 "시간 휴무"(특정 날짜의 일부 시간만 닫기)가 TimeSlot.is_active = false 로 처리돼
  모든 날짜에서 그 시간이 닫히던 결함. 날짜 단위 조치를 표현할 곳으로 calendar_blocks 를 쓴다.

변경 내용:
- calendar_blocks 가 없으면 모델과 같은 구조로 생성 (원격 DB에는 테이블이 없었음)
- calendar_blocks.time_slot_id (INTEGER, NULL 허용, time_slots.id FK, ON DELETE CASCADE) 추가
  - 값이 있으면 그 날짜의 그 시간만, NULL 이면 그 날짜 전체를 닫는다

데이터: 기존 행은 time_slot_id = NULL (기존 의미 '기간 전체 차단' 그대로). 데이터 손실 없음
downgrade: 시간 지정 블록은 예전 구조로 표현할 수 없으므로 삭제한 뒤 컬럼 제거
           (남기면 '하루 전체 차단'으로 의미가 바뀐다). 테이블 자체는 모델에 있으므로 남긴다
"""
from alembic import op

revision = "n8o9p0q1r2s3"
down_revision = "m7n8o9p0q1r2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # calendar_blocks 는 모델에만 있고 마이그레이션으로 만든 적이 없다. 초기 DB 생성(create_all) 시점에
    # 모델이 없었던 DB(원격)에는 테이블이 없으므로 모델과 같은 구조로 만든다. 이미 있으면 그대로 둔다
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.calendar_blocks (
            id          SERIAL PRIMARY KEY,
            calendar_id INTEGER NOT NULL REFERENCES public.calendars(id),
            start_date  DATE NOT NULL,
            end_date    DATE NOT NULL,
            reason      TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_calendar_blocks_calendar_id ON public.calendar_blocks (calendar_id)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_calendar_blocks_range ON public.calendar_blocks (calendar_id, start_date, end_date)"
    )
    # init 마이그레이션이 현재 모델로 create_all 하므로 빈 DB에는 컬럼이 이미 있을 수 있다
    op.execute(
        "ALTER TABLE public.calendar_blocks "
        "ADD COLUMN IF NOT EXISTS time_slot_id INTEGER NULL "
        "REFERENCES public.time_slots(id) ON DELETE CASCADE"
    )


def downgrade() -> None:
    op.execute("DELETE FROM public.calendar_blocks WHERE time_slot_id IS NOT NULL")
    op.execute("ALTER TABLE public.calendar_blocks DROP COLUMN IF EXISTS time_slot_id")
