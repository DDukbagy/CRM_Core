"""delete legacy posts data (moved copies and backups)

Revision ID: q1r2s3t4u5v6
Revises: p0q1r2s3t4u5
Create Date: 2026-10-01 00:00:00.000000

배경:
- o9p0q1r2s3t4 로 예전 posts 도메인 게시물을 새 posts 로 옮겼으나, 사용자 결정(2026-10-01)으로
  예전 게시물 데이터를 옮긴 것과 백업까지 모두 지운다.

변경 내용 (legacy_posts 가 있을 때만):
1. 새 posts 에서 legacy_posts 와 같은 ID 의 게시물 삭제
   → post_comments·post_likes·post_media 는 FK ON DELETE CASCADE 로 함께 삭제
2. 그 게시물을 가리키는 notifications 삭제 (related_post_id 는 FK 가 없어 직접 삭제)
3. 예전 테이블 삭제: post_consents(예전 게시물 공개 동의 기록, 코드에서 쓰지 않음, legacy_posts 에 FK),
   legacy_match_requests, legacy_post_likes, legacy_comments, legacy_post_media, legacy_posts
4. 예전 테이블에서만 쓰던 enum 타입 삭제: posttype, poststatus, matchstatus (다른 곳에서 쓰면 남김)

빈 DB(legacy_posts 없음)에서는 아무것도 하지 않는다.
downgrade: 지운 데이터는 되돌릴 수 없다. 예외를 내어 이 지점 아래로 내려가지 못하게 한다
           (l6m7n8o9p0q1 의 downgrade 는 legacy_* 테이블이 있어야 동작)
"""
from alembic import op

revision = "q1r2s3t4u5v6"
down_revision = "p0q1r2s3t4u5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DO $$
    DECLARE
        t text;
        n_posts integer;
        n_notifications integer;
    BEGIN
        IF to_regclass('public.legacy_posts') IS NULL THEN
            RETURN;
        END IF;

        DELETE FROM public.notifications WHERE related_post_id IN (SELECT id FROM public.legacy_posts);
        GET DIAGNOSTICS n_notifications = ROW_COUNT;
        DELETE FROM public.posts WHERE id IN (SELECT id FROM public.legacy_posts);
        GET DIAGNOSTICS n_posts = ROW_COUNT;

        FOREACH t IN ARRAY ARRAY['post_consents', 'legacy_match_requests', 'legacy_post_likes',
                                 'legacy_comments', 'legacy_post_media', 'legacy_posts'] LOOP
            EXECUTE format('DROP TABLE IF EXISTS public.%I', t);
        END LOOP;

        FOREACH t IN ARRAY ARRAY['posttype', 'poststatus', 'matchstatus'] LOOP
            IF EXISTS (SELECT 1 FROM pg_type ty JOIN pg_namespace ns ON ns.oid = ty.typnamespace
                       WHERE ns.nspname = 'public' AND ty.typname = t)
               AND NOT EXISTS (SELECT 1 FROM pg_attribute a JOIN pg_type ty ON ty.oid = a.atttypid
                               JOIN pg_class c ON c.oid = a.attrelid
                               WHERE ty.typname = t AND c.relkind IN ('r', 'v', 'm') AND NOT a.attisdropped) THEN
                EXECUTE format('DROP TYPE public.%I', t);
            END IF;
        END LOOP;

        RAISE NOTICE 'drop_legacy_posts: posts %, notifications % deleted; legacy tables dropped', n_posts, n_notifications;
    END $$;
    """)


def downgrade() -> None:
    raise RuntimeError(
        "q1r2s3t4u5v6 는 예전 게시물 데이터를 삭제한 마이그레이션이라 되돌릴 수 없습니다 (legacy_* 테이블 없음)."
    )
