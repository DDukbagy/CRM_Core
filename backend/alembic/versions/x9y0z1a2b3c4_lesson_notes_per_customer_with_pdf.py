"""lesson notes per customer (optional booking, PDF); move FEEDBACK posts into lesson notes

레슨 노트를 예약과 상관없이 고객별로 쓰고, 수기 노트 스캔(PDF)도 올릴 수 있게 한다.
피드백 게시물(posts.type='FEEDBACK')은 성격이 같아 레슨 노트로 통합한다 (사용자 결정 2026-10-04).

- lesson_notes: customer_id(필수, 기존 행은 예약의 고객으로 채움), title, file_key, file_name 추가
  content·booking_id NULL 허용, 예약 FK 는 ON DELETE SET NULL (예약이 지워져도 노트는 남김)
  ck_lesson_notes_body: 내용 또는 PDF 중 하나는 있어야 함
- FEEDBACK 게시물 → lesson_notes (고객에게 공유됨) 로 옮기고 게시물·그 게시물의 알림 삭제
  사진·영상이 붙은 피드백은 노트로 옮길 수 없어 있으면 중단 (데이터 보호)

downgrade: 예약에 연결되지 않은 노트는 FEEDBACK 게시물로 되돌리고 구조를 되돌린다
          (PDF 만 있는 노트는 게시물로 옮길 수 없어 있으면 중단)

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
"""
from typing import Sequence, Union

from alembic import op

revision: str = "x9y0z1a2b3c4"
down_revision: Union[str, None] = "w8x9y0z1a2b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fk(table: str, column: str, ref: str) -> None:
    op.execute(
        f"""
        DO $$
        DECLARE r record;
        BEGIN
          FOR r IN
            SELECT c.conname FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
            WHERE c.contype = 'f' AND c.conrelid = 'public.{table}'::regclass
              AND c.confrelid = 'public.{ref}'::regclass AND a.attname = '{column}'
          LOOP
            EXECUTE format('ALTER TABLE public.{table} DROP CONSTRAINT %I', r.conname);
          END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM public.posts p JOIN public.post_media m ON m.post_id = p.id WHERE p.type = 'FEEDBACK')
             OR EXISTS (SELECT 1 FROM public.posts WHERE type = 'FEEDBACK' AND (media_url IS NOT NULL OR customer_id IS NULL)) THEN
            RAISE EXCEPTION '사진·영상이 있거나 고객이 없는 피드백 게시물이 있어 중단합니다. 먼저 정리하세요.';
          END IF;
        END $$;
        """
    )
    # 빈 DB 에서는 init(create_all)이 현재 모델로 이미 만든다 → IF NOT EXISTS / 존재 확인
    op.execute("ALTER TABLE public.lesson_notes ADD COLUMN IF NOT EXISTS customer_id UUID")
    op.execute("ALTER TABLE public.lesson_notes ADD COLUMN IF NOT EXISTS title TEXT")
    op.execute("ALTER TABLE public.lesson_notes ADD COLUMN IF NOT EXISTS file_key TEXT")
    op.execute("ALTER TABLE public.lesson_notes ADD COLUMN IF NOT EXISTS file_name TEXT")
    op.execute(
        "UPDATE public.lesson_notes n SET customer_id = b.guest_id FROM public.bookings b "
        "WHERE n.customer_id IS NULL AND b.id = n.booking_id"
    )
    op.execute("ALTER TABLE public.lesson_notes ALTER COLUMN customer_id SET NOT NULL")
    _drop_fk("lesson_notes", "customer_id", "users")
    op.execute(
        "ALTER TABLE public.lesson_notes ADD CONSTRAINT lesson_notes_customer_id_fkey "
        "FOREIGN KEY (customer_id) REFERENCES public.users(id) ON DELETE CASCADE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_lesson_notes_customer_id ON public.lesson_notes(customer_id)")

    op.execute("ALTER TABLE public.lesson_notes ALTER COLUMN content DROP NOT NULL")
    op.execute("ALTER TABLE public.lesson_notes ALTER COLUMN booking_id DROP NOT NULL")
    _drop_fk("lesson_notes", "booking_id", "bookings")
    op.execute(
        "ALTER TABLE public.lesson_notes ADD CONSTRAINT lesson_notes_booking_id_fkey "
        "FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE public.lesson_notes DROP CONSTRAINT IF EXISTS ck_lesson_notes_body")
    op.execute(
        "ALTER TABLE public.lesson_notes ADD CONSTRAINT ck_lesson_notes_body "
        "CHECK (content IS NOT NULL OR file_key IS NOT NULL)"
    )

    # 피드백 게시물 → 레슨 노트
    op.execute(
        """
        INSERT INTO public.lesson_notes (customer_id, instructor_id, title, content, is_shared, created_at, updated_at)
        SELECT customer_id, instructor_id, title, COALESCE(content, title, ''), true, created_at, updated_at
        FROM public.posts WHERE type = 'FEEDBACK'
        """
    )
    op.execute(
        "DELETE FROM public.notifications WHERE related_post_id IN (SELECT id FROM public.posts WHERE type = 'FEEDBACK')"
    )
    op.execute("DELETE FROM public.posts WHERE type = 'FEEDBACK'")


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM public.lesson_notes WHERE booking_id IS NULL AND content IS NULL) THEN
            RAISE EXCEPTION 'PDF 만 있는 레슨 노트가 있어 되돌릴 수 없습니다.';
          END IF;
        END $$;
        """
    )
    op.execute(
        """
        INSERT INTO public.posts (instructor_id, created_by_user_id, type, title, content, customer_id, is_public, created_at, updated_at)
        SELECT instructor_id, instructor_id, 'FEEDBACK', title, content, customer_id, false, created_at, updated_at
        FROM public.lesson_notes WHERE booking_id IS NULL
        """
    )
    op.execute("DELETE FROM public.lesson_notes WHERE booking_id IS NULL")
    op.execute("ALTER TABLE public.lesson_notes DROP CONSTRAINT IF EXISTS ck_lesson_notes_body")
    op.execute("UPDATE public.lesson_notes SET content = COALESCE(content, '')")
    op.execute("ALTER TABLE public.lesson_notes ALTER COLUMN content SET NOT NULL")
    _drop_fk("lesson_notes", "booking_id", "bookings")
    op.execute("ALTER TABLE public.lesson_notes ALTER COLUMN booking_id SET NOT NULL")
    op.execute(
        "ALTER TABLE public.lesson_notes ADD CONSTRAINT lesson_notes_booking_id_fkey "
        "FOREIGN KEY (booking_id) REFERENCES public.bookings(id) ON DELETE CASCADE"
    )
    op.execute("DROP INDEX IF EXISTS public.ix_lesson_notes_customer_id")
    for col in ("file_name", "file_key", "title", "customer_id"):
        op.execute(f"ALTER TABLE public.lesson_notes DROP COLUMN IF EXISTS {col}")
