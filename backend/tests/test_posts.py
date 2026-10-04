from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.domains.posts.router as posts_router
from app.domains.notifications.models import Notification, NotificationType
from app.domains.posts.models import Post, PostComment, PostMedia

S3_URL = "https://test-bucket.s3.ap-northeast-2.amazonaws.com/instructor-posts/u1/photo.jpg"
S3_KEY = "instructor-posts/u1/photo.jpg"


async def _insert_user(session: AsyncSession, role: str, manager_id: uuid.UUID | None = None) -> uuid.UUID:
    user_id = uuid.uuid4()
    await session.execute(
        text(
            """
            insert into public.users (id, username, email, display_name, is_active, status, role, manager_id, feedback_consent)
            values (:id, :username, :email, :display_name, true, 'ACTIVE', :role, :manager_id, true)
            """
        ),
        {
            "id": str(user_id),
            "username": f"post-{user_id.hex[:8]}",
            "email": f"post-{user_id.hex[:8]}@example.com",
            "display_name": f"post-{user_id.hex[:8]}",
            "role": role,
            "manager_id": str(manager_id) if manager_id else None,
        },
    )
    await session.commit()
    return user_id


@pytest_asyncio.fixture
async def public_post(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> Post:
    """다른 강사가 쓴 공개 홍보 게시물"""
    async with db_conn_and_sessionmaker() as session:
        owner_id = await _insert_user(session, "INSTRUCTOR")
        post = Post(instructor_id=owner_id, type="PROMOTION", title="공개 홍보", content="hello", is_public=True)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post


@pytest_asyncio.fixture
async def others_feedback(db_conn_and_sessionmaker: async_sessionmaker[AsyncSession]) -> Post:
    """다른 고객이 대상인 비공개 피드백"""
    async with db_conn_and_sessionmaker() as session:
        owner_id = await _insert_user(session, "INSTRUCTOR")
        customer_id = await _insert_user(session, "CUSTOMER", manager_id=owner_id)
        post = Post(instructor_id=owner_id, type="FEEDBACK", title="비공개", customer_id=customer_id, is_public=False)
        session.add(post)
        await session.commit()
        await session.refresh(post)
        return post


# ── 작성 ──────────────────────────────────────────────────────

@pytest.mark.asyncio
@pytest.mark.parametrize("post_type", ["PROMOTION", "NOTICE", "COMMUNITY"])
async def test_instructor_creates_public_types(instructor_client, post_type: str):
    r = await instructor_client.post("/posts", json={"type": post_type, "title": "t"})
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["type"] == post_type
    assert data["is_public"] is True
    assert data["like_count"] == 0 and data["comment_count"] == 0


@pytest.mark.asyncio
async def test_feedback_posts_moved_to_lesson_notes(instructor_client, managed_customer_id: uuid.UUID):
    """피드백은 레슨 노트로 통합 (2026-10-04) — 게시물로는 만들 수 없다"""
    r = await instructor_client.post(
        "/posts", json={"type": "FEEDBACK", "title": "fb", "customer_id": str(managed_customer_id)}
    )
    assert r.status_code == 400 and "레슨노트" in r.text


@pytest.mark.asyncio
async def test_invalid_type_is_rejected(instructor_client):
    r = await instructor_client.post("/posts", json={"type": "MEETUP", "title": "t"})
    assert r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_customer_cannot_create_post(client):
    r = await client.post("/posts", json={"type": "COMMUNITY", "title": "t"})
    assert r.status_code == 403, r.text


# ── 목록·피드·검색 ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_feed_and_search_show_only_visible_posts(client, public_post: Post, others_feedback: Post):
    listed = {p["id"] for p in (await client.get("/posts")).json()}
    assert str(public_post.id) in listed
    assert str(others_feedback.id) not in listed

    feed = {p["id"] for p in (await client.get("/posts/feed")).json()}
    assert str(public_post.id) in feed
    assert str(others_feedback.id) not in feed

    found = {p["id"] for p in (await client.get("/posts/search", params={"q": "공개 홍보"})).json()}
    assert str(public_post.id) in found
    hidden = {p["id"] for p in (await client.get("/posts/search", params={"q": "비공개"})).json()}
    assert str(others_feedback.id) not in hidden


@pytest.mark.asyncio
async def test_private_feedback_is_hidden_from_other_customers(client, others_feedback: Post):
    assert (await client.get(f"/posts/{others_feedback.id}/comments")).status_code == 403
    assert (await client.post(f"/posts/{others_feedback.id}/comments", json={"content": "x"})).status_code == 403
    assert (await client.post(f"/posts/{others_feedback.id}/like")).status_code == 403


# ── 댓글·대댓글 ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_comment_reply_edit_delete(client, public_post: Post, db_conn_and_sessionmaker):
    base = f"/posts/{public_post.id}/comments"

    r = await client.post(base, json={"content": "첫 댓글"})
    assert r.status_code == 201, r.text
    comment = r.json()
    assert isinstance(comment["id"], int) and comment["parent_id"] is None

    r = await client.post(base, json={"content": "답글", "parent_id": comment["id"]})
    assert r.status_code == 201, r.text
    reply = r.json()
    assert reply["parent_id"] == comment["id"]

    # 다른 게시물의 댓글을 부모로 지정할 수 없다
    r = await client.post(base, json={"content": "x", "parent_id": 999_999_999})
    assert r.status_code == 400, r.text

    r = await client.patch(f"/posts/comments/{comment['id']}", json={"content": "수정됨"})
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "수정됨"

    listed = (await client.get(base)).json()
    assert [c["id"] for c in listed] == [comment["id"], reply["id"]]

    # 게시물 주인에게 댓글·답글 알림이 쌓인다
    async with db_conn_and_sessionmaker() as session:
        res = await session.execute(
            select(Notification.notification_type).where(Notification.recipient_id == public_post.instructor_id)
        )
        assert sorted(t.value for (t,) in res.all()) == ["COMMENT", "REPLY"]

    # 부모 댓글을 지우면 "삭제된 댓글입니다"로 남고 답글은 그대로다
    r = await client.delete(f"/posts/comments/{comment['id']}")
    assert r.status_code == 204, r.text
    listed = (await client.get(base)).json()
    assert [c["id"] for c in listed] == [comment["id"], reply["id"]]
    deleted, kept = listed
    assert deleted["is_deleted"] is True
    assert deleted["content"] == "삭제된 댓글입니다"
    assert deleted["user_name"] is None
    assert kept["is_deleted"] is False and kept["content"] == "답글" and kept["parent_id"] == comment["id"]

    # 원문은 DB에서도 지워진다
    async with db_conn_and_sessionmaker() as session:
        row = await session.get(PostComment, comment["id"])
        assert row.content == "" and row.deleted_at is not None


@pytest.mark.asyncio
async def test_deleted_comment_rules(client, public_post: Post, db_conn_and_sessionmaker):
    base = f"/posts/{public_post.id}/comments"
    first = (await client.post(base, json={"content": "지울 댓글입니다"})).json()
    await client.post(base, json={"content": "남길 댓글"})
    assert (await client.get(f"/posts/{public_post.id}")).json()["comment_count"] == 2

    assert (await client.delete(f"/posts/comments/{first['id']}")).status_code == 204

    # 댓글 수에서 빠진다
    assert (await client.get(f"/posts/{public_post.id}")).json()["comment_count"] == 1
    # 이미 삭제된 댓글은 수정·재삭제할 수 없고, 답글도 달 수 없다
    assert (await client.patch(f"/posts/comments/{first['id']}", json={"content": "x"})).status_code == 404
    assert (await client.delete(f"/posts/comments/{first['id']}")).status_code == 404
    assert (await client.post(base, json={"content": "x", "parent_id": first["id"]})).status_code == 400

    # 지운 댓글의 알림(원문 미리보기 포함)만 사라지고, 다른 댓글 알림은 남는다
    async with db_conn_and_sessionmaker() as session:
        contents = (
            await session.execute(
                select(Notification.content).where(Notification.related_post_id == public_post.id)
            )
        ).scalars().all()
    assert len(contents) == 1
    assert "남길 댓글" in contents[0]
    assert all("지울 댓글" not in c for c in contents)


@pytest.mark.asyncio
async def test_admin_deletes_others_comment_as_soft_delete(admin_client, public_post: Post, db_conn_and_sessionmaker):
    async with db_conn_and_sessionmaker() as session:
        other = await _insert_user(session, "CUSTOMER")
        comment = PostComment(post_id=public_post.id, user_id=other, content="관리자가 지울 댓글")
        session.add(comment)
        await session.commit()
        await session.refresh(comment)

    assert (await admin_client.delete(f"/posts/comments/{comment.id}")).status_code == 204
    listed = (await admin_client.get(f"/posts/{public_post.id}/comments")).json()
    assert [(c["id"], c["is_deleted"], c["content"]) for c in listed] == [(comment.id, True, "삭제된 댓글입니다")]


@pytest.mark.asyncio
async def test_cannot_edit_or_delete_others_comment(client, public_post: Post, db_conn_and_sessionmaker):
    async with db_conn_and_sessionmaker() as session:
        other = await _insert_user(session, "CUSTOMER")
        comment = PostComment(post_id=public_post.id, user_id=other, content="남의 댓글")
        session.add(comment)
        await session.commit()
        await session.refresh(comment)

    assert (await client.patch(f"/posts/comments/{comment.id}", json={"content": "x"})).status_code == 403
    assert (await client.delete(f"/posts/comments/{comment.id}")).status_code == 403


# ── 좋아요 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_like_toggle_and_counts(client, public_post: Post):
    r = await client.post(f"/posts/{public_post.id}/like")
    assert r.status_code == 200 and r.json()["is_liked"] is True

    mine = next(p for p in (await client.get("/posts")).json() if p["id"] == str(public_post.id))
    assert mine["like_count"] == 1 and mine["is_liked"] is True

    r = await client.post(f"/posts/{public_post.id}/like")
    assert r.json()["is_liked"] is False

    mine = next(p for p in (await client.get("/posts")).json() if p["id"] == str(public_post.id))
    assert mine["like_count"] == 0 and mine["is_liked"] is False


@pytest.mark.asyncio
async def test_unlike_removes_like_notification(client, public_post: Post, db_conn_and_sessionmaker):
    async def like_notifications() -> int:
        async with db_conn_and_sessionmaker() as session:
            rows = await session.execute(
                select(Notification).where(
                    Notification.related_post_id == public_post.id,
                    Notification.notification_type == NotificationType.LIKE,
                )
            )
            return len(rows.scalars().all())

    await client.post(f"/posts/{public_post.id}/like")
    assert await like_notifications() == 1

    # 취소하면 알림 없이, 좋아요로 생긴 알림도 사라진다
    r = await client.post(f"/posts/{public_post.id}/like")
    assert r.json()["is_liked"] is False
    assert await like_notifications() == 0

    # 다시 눌러도 알림은 하나만 남는다
    await client.post(f"/posts/{public_post.id}/like")
    assert await like_notifications() == 1


# ── 미디어 ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_media_is_served_with_presigned_url(instructor_client, db_conn_and_sessionmaker, monkeypatch):
    monkeypatch.setattr(posts_router, "create_presigned_url", lambda key: f"https://signed.example/{key}?sig=1")

    r = await instructor_client.post(
        "/posts",
        json={"type": "PROMOTION", "media_items": [{"url": S3_URL, "media_type": "IMAGE"}]},
    )
    assert r.status_code == 201, r.text
    post = r.json()
    assert post["media_items"][0]["url"] == f"https://signed.example/{S3_KEY}?sig=1"

    # 앱이 임시 서명 주소를 그대로 되돌려 보내도 서명 없는 주소와 키만 저장한다
    r = await instructor_client.patch(
        f"/posts/{post['id']}",
        json={"media_items": [{"url": S3_URL + "?X-Amz-Signature=abc", "media_type": "IMAGE"}]},
    )
    assert r.status_code == 200, r.text

    async with db_conn_and_sessionmaker() as session:
        rows = (await session.execute(select(PostMedia).where(PostMedia.post_id == uuid.UUID(post["id"])))).scalars().all()
        assert [(m.url, m.s3_key) for m in rows] == [(S3_URL, S3_KEY)]


@pytest.mark.asyncio
async def test_delete_post_removes_s3_objects(instructor_client, monkeypatch):
    deleted: list[str] = []
    monkeypatch.setattr(posts_router, "delete_file_from_s3", lambda key: deleted.append(key) or True)

    r = await instructor_client.post(
        "/posts",
        json={"type": "PROMOTION", "media_items": [{"url": S3_URL, "media_type": "IMAGE"}]},
    )
    post_id = r.json()["id"]

    assert (await instructor_client.delete(f"/posts/{post_id}")).status_code == 204
    assert deleted == [S3_KEY]
    assert (await instructor_client.get(f"/posts/{post_id}")).status_code == 404


@pytest.mark.asyncio
async def test_delete_post_removes_its_notifications(instructor_client, instructor_id, public_post: Post, db_conn_and_sessionmaker):
    r = await instructor_client.post("/posts", json={"type": "PROMOTION", "title": "지울 글"})
    post_id = uuid.UUID(r.json()["id"])

    async with db_conn_and_sessionmaker() as session:
        sender = await _insert_user(session, "CUSTOMER")
        session.add(Notification(recipient_id=instructor_id, sender_id=sender, notification_type=NotificationType.COMMENT, related_post_id=post_id, content="댓글"))
        session.add(Notification(recipient_id=instructor_id, sender_id=sender, notification_type=NotificationType.LIKE, related_post_id=post_id, content="좋아요"))
        session.add(Notification(recipient_id=public_post.instructor_id, sender_id=sender, notification_type=NotificationType.LIKE, related_post_id=public_post.id, content="다른 글"))
        await session.commit()

    assert (await instructor_client.delete(f"/posts/{post_id}")).status_code == 204

    async with db_conn_and_sessionmaker() as session:
        remaining = (await session.execute(select(Notification.related_post_id))).scalars().all()
    assert post_id not in remaining
    assert public_post.id in remaining  # 다른 게시물의 알림은 그대로


@pytest.mark.asyncio
async def test_instructor_cannot_edit_others_post(instructor_client, public_post: Post):
    r = await instructor_client.patch(f"/posts/{public_post.id}", json={"title": "hack"})
    assert r.status_code == 403, r.text
    assert (await instructor_client.delete(f"/posts/{public_post.id}")).status_code == 403
