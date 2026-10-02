"""merge posts and content domains into one posts domain

Revision ID: l6m7n8o9p0q1
Revises: k5l6m7n8o9p0
Create Date: 2026-09-30 00:00:00.000000

변경 내용:
- 기준 테이블은 content 도메인 쪽(앱이 사용 중)
  - instructor_posts       → posts
  - instructor_post_media  → post_media
  - post_comments          → 그대로 (parent_id, updated_at 추가)
  - post_likes             → 신설
- 예전 posts 도메인 테이블은 삭제하지 않고 legacy_ 접두사로 보관
  - posts, post_media, comments, post_likes, match_requests → legacy_*
- posts.type CHECK를 PROMOTION / NOTICE / FEEDBACK / COMMUNITY 로 확장
- posts.created_by_user_id 추가 (콘텐츠 매니저 대리 작성)
- post_media.s3_key 추가 (조회용 임시 서명 URL 발급), 기존 S3 URL에서 채움
- 게시물 관련 FK의 ON DELETE 동작을 환경과 무관하게 동일하게 맞춤

주의:
- init 마이그레이션(91d68413f8d6)이 현재 모델로 create_all 하므로, 빈 DB에서는
  새 구조의 posts / post_comments / post_likes 가 이미 만들어져 있을 수 있다.
  이 경우(=posts 에 owner_user_id 컬럼이 없음) 비어 있는지 확인한 뒤 지우고,
  기존 DB와 같은 경로(instructor_posts → posts)로 다시 만든다.
- 데이터 삭제 없음. downgrade 는 이름과 추가 컬럼을 되돌린다.
"""
from alembic import op

revision = "l6m7n8o9p0q1"
down_revision = "k5l6m7n8o9p0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 예전 posts 도메인 테이블 정리 (보관 또는 빈 새 구조 제거)
    op.execute("""
    DO $$
    DECLARE
        t   text;
        r   record;
        n   bigint;
    BEGIN
        IF to_regclass('public.posts') IS NOT NULL THEN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'posts' AND column_name = 'owner_user_id'
            ) THEN
                -- 기존 DB: 예전 posts 도메인 테이블을 legacy_ 로 보관
                FOREACH t IN ARRAY ARRAY['match_requests', 'post_likes', 'comments', 'post_media', 'posts'] LOOP
                    IF to_regclass('public.' || t) IS NOT NULL THEN
                        EXECUTE format('ALTER TABLE public.%I RENAME TO %I', t, 'legacy_' || t);
                    END IF;
                END LOOP;
            ELSE
                -- 빈 DB: create_all 이 만든 새 구조 테이블. 비어 있을 때만 제거
                FOREACH t IN ARRAY ARRAY['post_likes', 'post_comments', 'post_media', 'posts'] LOOP
                    IF to_regclass('public.' || t) IS NOT NULL THEN
                        EXECUTE format('SELECT count(*) FROM public.%I', t) INTO n;
                        IF n > 0 THEN
                            RAISE EXCEPTION 'merge_posts: table % is not empty (% rows); manual check required', t, n;
                        END IF;
                        EXECUTE format('DROP TABLE public.%I CASCADE', t);
                    END IF;
                END LOOP;
            END IF;
        END IF;

        -- 보관 테이블의 제약·인덱스 이름이 새 테이블과 충돌하지 않게 접두사 부여
        FOR r IN
            SELECT c.conname, c.conrelid::regclass AS tbl
            FROM pg_constraint c
            JOIN pg_class k ON k.oid = c.conrelid
            JOIN pg_namespace ns ON ns.oid = k.relnamespace
            WHERE ns.nspname = 'public' AND k.relname LIKE 'legacy\\_%' AND c.conname NOT LIKE 'legacy\\_%'
        LOOP
            EXECUTE format('ALTER TABLE %s RENAME CONSTRAINT %I TO %I', r.tbl, r.conname, 'legacy_' || r.conname);
        END LOOP;
        FOR r IN
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'public' AND tablename LIKE 'legacy\\_%' AND indexname NOT LIKE 'legacy\\_%'
        LOOP
            EXECUTE format('ALTER INDEX public.%I RENAME TO %I', r.indexname, 'legacy_' || r.indexname);
        END LOOP;
    END $$;
    """)

    # 2. content 도메인 테이블을 posts 도메인 이름으로 변경
    op.execute("""
    DO $$
    DECLARE
        r record;
    BEGIN
        IF to_regclass('public.instructor_posts') IS NULL THEN
            RAISE EXCEPTION 'merge_posts: instructor_posts table not found';
        END IF;
        ALTER TABLE public.instructor_posts RENAME TO posts;

        IF to_regclass('public.instructor_post_media') IS NOT NULL THEN
            ALTER TABLE public.instructor_post_media RENAME TO post_media;
        END IF;
        IF to_regclass('public.instructor_post_media_id_seq') IS NOT NULL THEN
            ALTER SEQUENCE public.instructor_post_media_id_seq RENAME TO post_media_id_seq;
        END IF;

        -- 제약·인덱스 이름의 instructor_post 접두사를 post 로 변경
        FOR r IN
            SELECT c.conname, c.conrelid::regclass AS tbl
            FROM pg_constraint c
            WHERE c.conrelid IN ('public.posts'::regclass, 'public.post_media'::regclass)
              AND c.conname LIKE 'instructor\\_post%'
        LOOP
            EXECUTE format('ALTER TABLE %s RENAME CONSTRAINT %I TO %I',
                           r.tbl, r.conname, regexp_replace(r.conname, '^instructor_post', 'post'));
        END LOOP;
        FOR r IN
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'public' AND tablename IN ('posts', 'post_media')
              AND indexname LIKE '%instructor\\_post%'
        LOOP
            EXECUTE format('ALTER INDEX public.%I RENAME TO %I',
                           r.indexname, replace(r.indexname, 'instructor_post', 'post'));
        END LOOP;

        -- type CHECK: 기존 제약(이름이 환경마다 다를 수 있음)을 지우고 4종으로 다시 만든다
        FOR r IN
            SELECT conname FROM pg_constraint
            WHERE conrelid = 'public.posts'::regclass AND contype = 'c'
              AND pg_get_constraintdef(oid) ILIKE '%type%'
        LOOP
            EXECUTE format('ALTER TABLE public.posts DROP CONSTRAINT %I', r.conname);
        END LOOP;
    END $$;
    """)
    op.execute("""
        ALTER TABLE public.posts
        ADD CONSTRAINT chk_posts_type CHECK (type IN ('PROMOTION', 'NOTICE', 'FEEDBACK', 'COMMUNITY'))
    """)

    # 3. 컬럼 추가
    op.execute("ALTER TABLE public.posts ADD COLUMN IF NOT EXISTS created_by_user_id UUID")
    op.execute("ALTER TABLE public.post_media ADD COLUMN IF NOT EXISTS s3_key TEXT")
    op.execute("""
        UPDATE public.post_media
        SET s3_key = split_part(substring(url from '^https?://[^/]+\\.amazonaws\\.com/(.+)$'), '?', 1)
        WHERE s3_key IS NULL AND url ~ '^https?://[^/]+\\.amazonaws\\.com/.+'
    """)

    # 4. 댓글: 테이블 보장 + 대댓글·수정 시각
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.post_comments (
            id          SERIAL PRIMARY KEY,
            post_id     UUID NOT NULL,
            user_id     UUID NOT NULL,
            content     TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_comments_post_id ON public.post_comments (post_id)")
    op.execute("ALTER TABLE public.post_comments ADD COLUMN IF NOT EXISTS parent_id INTEGER")
    op.execute("ALTER TABLE public.post_comments ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()")
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_comments_parent_id ON public.post_comments (parent_id)")

    # 5. 좋아요
    op.execute("""
        CREATE TABLE IF NOT EXISTS public.post_likes (
            id          SERIAL PRIMARY KEY,
            post_id     UUID NOT NULL,
            user_id     UUID NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_post_likes_user_post UNIQUE (user_id, post_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_likes_post_id ON public.post_likes (post_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_post_likes_user_id ON public.post_likes (user_id)")

    # 6. FK를 환경과 무관하게 같은 이름·같은 ON DELETE 동작으로 다시 만든다
    op.execute("""
    DO $$
    DECLARE
        r    record;
        spec record;
    BEGIN
        FOR spec IN
            SELECT * FROM (VALUES
                ('posts',         'instructor_id',      'users',         'CASCADE'),
                ('posts',         'customer_id',        'users',         'SET NULL'),
                ('posts',         'created_by_user_id', 'users',         'SET NULL'),
                ('post_media',    'post_id',            'posts',         'CASCADE'),
                ('post_comments', 'post_id',            'posts',         'CASCADE'),
                ('post_comments', 'user_id',            'users',         'CASCADE'),
                ('post_comments', 'parent_id',          'post_comments', 'CASCADE'),
                ('post_likes',    'post_id',            'posts',         'CASCADE'),
                ('post_likes',    'user_id',            'users',         'CASCADE')
            ) AS v(tbl, col, ref, ondel)
        LOOP
            FOR r IN
                SELECT c.conname
                FROM pg_constraint c
                JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
                WHERE c.conrelid = ('public.' || spec.tbl)::regclass AND c.contype = 'f'
                  AND array_length(c.conkey, 1) = 1 AND a.attname = spec.col
            LOOP
                EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT %I', spec.tbl, r.conname);
            END LOOP;
            EXECUTE format(
                'ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES public.%I (id) ON DELETE %s',
                spec.tbl, spec.tbl || '_' || spec.col || '_fkey', spec.col, spec.ref, spec.ondel
            );
        END LOOP;
    END $$;
    """)


def downgrade() -> None:
    # 추가한 것 제거 (좋아요·대댓글·대리 작성자·s3_key 정보는 사라진다)
    op.execute("DROP TABLE IF EXISTS public.post_likes")
    op.execute("ALTER TABLE public.post_comments DROP COLUMN IF EXISTS parent_id")
    op.execute("ALTER TABLE public.post_comments DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE public.post_media DROP COLUMN IF EXISTS s3_key")
    op.execute("ALTER TABLE public.posts DROP COLUMN IF EXISTS created_by_user_id")
    op.execute("ALTER TABLE public.posts DROP CONSTRAINT IF EXISTS chk_posts_type")

    # 이름 되돌리기
    op.execute("""
    DO $$
    DECLARE
        t text;
        r record;
    BEGIN
        FOR r IN
            SELECT c.conname, c.conrelid::regclass AS tbl
            FROM pg_constraint c
            WHERE c.conrelid IN ('public.posts'::regclass, 'public.post_media'::regclass)
              AND (c.conname LIKE 'posts\\_%' OR c.conname LIKE 'post\\_media\\_%')
        LOOP
            EXECUTE format('ALTER TABLE %s RENAME CONSTRAINT %I TO %I',
                           r.tbl, r.conname, 'instructor_' || r.conname);
        END LOOP;
        FOR r IN
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'public' AND tablename IN ('posts', 'post_media')
              AND (indexname LIKE 'ix\\_posts\\_%' OR indexname LIKE 'ix\\_post\\_media\\_%')
        LOOP
            EXECUTE format('ALTER INDEX public.%I RENAME TO %I',
                           r.indexname, replace(r.indexname, 'ix_post', 'ix_instructor_post'));
        END LOOP;
        IF to_regclass('public.post_media_id_seq') IS NOT NULL THEN
            ALTER SEQUENCE public.post_media_id_seq RENAME TO instructor_post_media_id_seq;
        END IF;
        ALTER TABLE public.post_media RENAME TO instructor_post_media;
        ALTER TABLE public.posts RENAME TO instructor_posts;

        -- 보관했던 예전 테이블 복원
        FOR r IN
            SELECT c.conname, c.conrelid::regclass AS tbl
            FROM pg_constraint c
            JOIN pg_class k ON k.oid = c.conrelid
            JOIN pg_namespace ns ON ns.oid = k.relnamespace
            WHERE ns.nspname = 'public' AND k.relname LIKE 'legacy\\_%' AND c.conname LIKE 'legacy\\_%'
        LOOP
            EXECUTE format('ALTER TABLE %s RENAME CONSTRAINT %I TO %I',
                           r.tbl, r.conname, regexp_replace(r.conname, '^legacy_', ''));
        END LOOP;
        FOR r IN
            SELECT indexname FROM pg_indexes
            WHERE schemaname = 'public' AND tablename LIKE 'legacy\\_%' AND indexname LIKE 'legacy\\_%'
        LOOP
            EXECUTE format('ALTER INDEX public.%I RENAME TO %I',
                           r.indexname, regexp_replace(r.indexname, '^legacy_', ''));
        END LOOP;
        FOREACH t IN ARRAY ARRAY['posts', 'post_media', 'comments', 'post_likes', 'match_requests'] LOOP
            IF to_regclass('public.legacy_' || t) IS NOT NULL THEN
                EXECUTE format('ALTER TABLE public.%I RENAME TO %I', 'legacy_' || t, t);
            END IF;
        END LOOP;
    END $$;
    """)
