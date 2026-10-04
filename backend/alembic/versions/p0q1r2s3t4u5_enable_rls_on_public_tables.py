"""enable row level security on every public table that lacks it

Revision ID: p0q1r2s3t4u5
Revises: o9p0q1r2s3t4
Create Date: 2026-10-01 00:00:00.000000

배경:
- Supabase 는 public 스키마 테이블을 Data API(PostgREST)로 노출하고, anon·authenticated 역할에
  기본 권한(읽기·쓰기)을 준다. anon 키는 앱에 들어 있는 공개 값이므로 RLS 가 꺼진 테이블은
  누구나 API 로 읽고 쓸 수 있다.
- 원격 DB 확인(2026-10-01): chat_rooms, chat_messages, alembic_version 이 RLS 꺼짐.
  이번 마이그레이션들이 새로 만드는 post_likes, calendar_blocks 도 기본은 꺼짐.

변경 내용:
- public 스키마에서 RLS 가 꺼진 모든 테이블에 RLS 를 켠다 (정책 없음 = anon·authenticated 차단)
- 백엔드는 테이블 소유자(postgres, RLS 우회)로 접속하므로 영향 없음
- 웹이 Supabase 로 직접 읽는 users 는 이미 RLS + "본인 행 읽기" 정책이 있어 그대로

downgrade: 아무것도 하지 않는다. 보안 설정을 되돌리면 다시 노출되기 때문 (필요하면 수동으로 DISABLE)
"""
from alembic import op

revision = "p0q1r2s3t4u5"
down_revision = "o9p0q1r2s3t4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DO $$
    DECLARE
        r record;
    BEGIN
        FOR r IN
            SELECT c.relname
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity
        LOOP
            EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', r.relname);
            RAISE NOTICE 'enable_rls: %', r.relname;
        END LOOP;
    END $$;
    """)


def downgrade() -> None:
    pass
