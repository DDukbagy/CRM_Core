"""copy legacy posts domain data into the merged posts tables

Revision ID: o9p0q1r2s3t4
Revises: n8o9p0q1r2s3
Create Date: 2026-10-01 00:00:00.000000

배경:
- l6m7n8o9p0q1(병합)은 앱이 쓰던 content 쪽 테이블을 기준으로 삼고, 예전 posts 도메인 테이블은
  legacy_* 로 이름만 바꿔 보관했다. 원격 DB 확인 결과 실제 데이터가 예전 쪽에만 있어(게시물·댓글·좋아요,
  그리고 그 게시물을 가리키는 알림) 새 구조로 옮긴다. (2026-10-01 사용자 결정)

옮기는 규칙:
- legacy_posts → posts: 게시물 ID 그대로 (알림 related_post_id 가 계속 유효)
  - instructor_id = instructor_id 또는 owner_user_id, created_by_user_id = created_by_user_id 또는 owner_user_id
  - content = caption, is_public = (status = 'PUBLIC'), 작성·수정 시각 유지
  - FEEDBACK 은 대상 고객 정보가 없으므로 COMMUNITY 로 (새 구조의 FEEDBACK 은 특정 고객 대상 글)
- legacy_comments → post_comments: 새 정수 ID, 대댓글 연결은 대응표로 옮김
- legacy_post_likes → post_likes: 같은 (사용자, 게시물) 중복은 하나만
- 작성자·댓글 작성자가 users 에 없는 행은 옮기지 않는다 (FK). 옮기지 못한 개수는 NOTICE 로 남긴다
- legacy_* 원본은 그대로 둔다 (백업). 이미 옮겨진 게시물 ID는 건너뛴다 (다시 실행해도 중복 없음)

빈 DB(legacy_posts 없음)에서는 아무것도 하지 않는다.
downgrade: 옮겨 온 게시물(legacy_posts 에 있는 ID)을 지운다 → 댓글·좋아요·미디어는 FK CASCADE 로 함께 삭제.
           legacy_* 원본은 남아 있으므로 데이터 손실 없음
"""
from alembic import op

revision = "o9p0q1r2s3t4"
down_revision = "n8o9p0q1r2s3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DO $$
    DECLARE
        r record;
        new_id integer;
        n_posts integer; n_posts_skipped integer;
        n_comments integer := 0; n_comments_skipped integer;
        n_likes integer;
    BEGIN
        IF to_regclass('public.legacy_posts') IS NULL THEN
            RETURN;
        END IF;

        -- 1. 게시물
        INSERT INTO public.posts
            (id, instructor_id, created_by_user_id, type, title, content, customer_id, is_public, created_at, updated_at)
        SELECT p.id,
               COALESCE(p.instructor_id, p.owner_user_id),
               COALESCE(p.created_by_user_id, p.owner_user_id),
               CASE WHEN p.post_type::text = 'FEEDBACK' THEN 'COMMUNITY' ELSE p.post_type::text END,
               p.title,
               p.caption,
               NULL,
               p.status::text = 'PUBLIC',
               p.created_at,
               p.updated_at
        FROM public.legacy_posts p
        JOIN public.users u ON u.id = COALESCE(p.instructor_id, p.owner_user_id)
        WHERE NOT EXISTS (SELECT 1 FROM public.posts x WHERE x.id = p.id);
        GET DIAGNOSTICS n_posts = ROW_COUNT;
        SELECT count(*) INTO n_posts_skipped
        FROM public.legacy_posts p
        WHERE NOT EXISTS (SELECT 1 FROM public.posts x WHERE x.id = p.id);

        -- 2. 댓글 (예전 UUID → 새 정수 ID 대응표, 대댓글은 부모가 먼저 오도록 작성 순)
        IF to_regclass('public.legacy_comments') IS NOT NULL THEN
            CREATE TEMP TABLE _comment_map (old_id uuid PRIMARY KEY, new_id integer NOT NULL) ON COMMIT DROP;
            FOR r IN
                SELECT c.*
                FROM public.legacy_comments c
                JOIN public.posts p ON p.id = c.post_id
                JOIN public.users u ON u.id = c.user_id
                WHERE NOT EXISTS (
                    SELECT 1 FROM public.post_comments x
                    WHERE x.post_id = c.post_id AND x.user_id = c.user_id AND x.created_at = c.created_at
                )
                ORDER BY c.created_at, c.id
            LOOP
                INSERT INTO public.post_comments (post_id, user_id, content, created_at, updated_at)
                VALUES (r.post_id, r.user_id, r.content, r.created_at, r.updated_at)
                RETURNING id INTO new_id;
                INSERT INTO _comment_map VALUES (r.id, new_id);
                n_comments := n_comments + 1;
            END LOOP;

            UPDATE public.post_comments pc
            SET parent_id = pm.new_id
            FROM public.legacy_comments c
            JOIN _comment_map cm ON cm.old_id = c.id
            JOIN _comment_map pm ON pm.old_id = c.parent_id
            WHERE pc.id = cm.new_id;

            SELECT count(*) - n_comments INTO n_comments_skipped FROM public.legacy_comments;
        END IF;

        -- 3. 좋아요
        n_likes := 0;
        IF to_regclass('public.legacy_post_likes') IS NOT NULL THEN
            INSERT INTO public.post_likes (post_id, user_id, created_at)
            SELECT l.post_id, l.user_id, l.created_at
            FROM public.legacy_post_likes l
            JOIN public.posts p ON p.id = l.post_id
            JOIN public.users u ON u.id = l.user_id
            ON CONFLICT (user_id, post_id) DO NOTHING;
            GET DIAGNOSTICS n_likes = ROW_COUNT;
        END IF;

        RAISE NOTICE 'copy_legacy_posts: posts % (not copied %), comments % (not copied %), likes %',
            n_posts, n_posts_skipped, n_comments, COALESCE(n_comments_skipped, 0), n_likes;
    END $$;
    """)


def downgrade() -> None:
    op.execute("""
    DO $$
    BEGIN
        IF to_regclass('public.legacy_posts') IS NOT NULL THEN
            DELETE FROM public.posts WHERE id IN (SELECT id FROM public.legacy_posts);
        END IF;
    END $$;
    """)
