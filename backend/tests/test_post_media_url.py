"""게시물 미디어 주소 검사 (docs/worklog/post-media-url-and-csp.md 2절 명세 1~6)

게시물의 미디어 주소(url)는 화면이 그대로 이미지·영상 주소로 쓰고, S3 주소면 서버가 그 키로 임시 서명 주소를 만들어 준다.
그래서 "우리 버킷의 게시물 폴더(instructor-posts/)에 있는 https 주소"만 받는다.

준비: 이 파일에서 우리 버킷은 test-bucket (ap-northeast-2) 이다 (bucket fixture)
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

import app.core.s3 as s3

pytestmark = pytest.mark.asyncio

OURS = "https://test-bucket.s3.ap-northeast-2.amazonaws.com"
GOOD = f"{OURS}/instructor-posts/u1/photo.jpg"


@pytest.fixture(autouse=True)
def bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(s3, "BUCKET_NAME", "test-bucket")
    monkeypatch.setattr(s3, "REGION", "ap-northeast-2")


def _post(url: str, media_type: str = "IMAGE") -> dict:
    return {"type": "PROMOTION", "media_items": [{"url": url, "media_type": media_type}]}


async def _media_count(db) -> int:
    async with db() as s:
        return (await s.execute(text("select count(*) from public.post_media"))).scalar_one()


# 명세 1. 우리 버킷의 게시물 폴더에 있는 https 주소는 → 201 로 저장된다 (임시 서명이 붙은 주소도 같다)
@pytest.mark.parametrize("url", [GOOD, GOOD + "?X-Amz-Signature=abc"])
async def test_spec1_우리_버킷의_게시물_주소는_저장(instructor_client, db_conn_and_sessionmaker, url):
    r = await instructor_client.post("/posts", json=_post(url))
    assert r.status_code == 201, r.text
    assert await _media_count(db_conn_and_sessionmaker) == 1


# 명세 2. https 가 아니거나(http, javascript:, data:) 다른 사이트의 주소면 → 400 으로 거부되고 게시물은 만들어지지 않는다
@pytest.mark.parametrize("url", [
    GOOD.replace("https://", "http://"),
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "https://evil.example/photo.jpg",
    "https://test-bucket.s3.ap-northeast-2.amazonaws.com.evil.example/instructor-posts/u1/photo.jpg",
])
async def test_spec2_다른_곳의_주소는_거부(instructor_client, db_conn_and_sessionmaker, url):
    r = await instructor_client.post("/posts", json=_post(url))
    assert r.status_code == 400, r.text
    assert (await instructor_client.get("/posts/me")).json() == []
    assert await _media_count(db_conn_and_sessionmaker) == 0


# 명세 3. 다른 버킷의 S3 주소면 → 400 (같은 키로 우리 버킷의 서명 주소가 만들어지면 안 된다)
async def test_spec3_다른_버킷의_주소는_거부(instructor_client, db_conn_and_sessionmaker):
    r = await instructor_client.post("/posts", json=_post("https://other-bucket.s3.ap-northeast-2.amazonaws.com/instructor-posts/u1/photo.jpg"))
    assert r.status_code == 400, r.text
    assert await _media_count(db_conn_and_sessionmaker) == 0


# 명세 4. 우리 버킷이지만 게시물 폴더가 아닌 주소(레슨노트 PDF 등)면 → 400 (남의 비공개 파일의 서명 주소를 얻을 수 없다)
@pytest.mark.parametrize("key", ["lesson-notes/someone/note.pdf", "instructor-posts/../lesson-notes/someone/note.pdf", ""])
async def test_spec4_게시물_폴더_밖의_파일은_거부(instructor_client, db_conn_and_sessionmaker, key):
    r = await instructor_client.post("/posts", json=_post(f"{OURS}/{key}"))
    assert r.status_code == 400, r.text
    assert await _media_count(db_conn_and_sessionmaker) == 0


# 명세 5. 게시물을 수정할 때도 같은 규칙이다 → 400 이고 기존 미디어는 그대로 남는다
async def test_spec5_수정할_때도_같은_규칙(instructor_client, db_conn_and_sessionmaker):
    post = (await instructor_client.post("/posts", json=_post(GOOD))).json()

    r = await instructor_client.patch(f"/posts/{post['id']}", json={"media_items": [{"url": "https://evil.example/x.jpg", "media_type": "IMAGE"}]})
    assert r.status_code == 400, r.text
    async with db_conn_and_sessionmaker() as s:
        urls = (await s.execute(text("select url from public.post_media"))).scalars().all()
    assert urls == [GOOD]


# 명세 6. 미디어 종류가 IMAGE·VIDEO 가 아니면 → 422
async def test_spec6_미디어_종류는_IMAGE_VIDEO만(instructor_client, db_conn_and_sessionmaker):
    r = await instructor_client.post("/posts", json=_post(GOOD, media_type="SCRIPT"))
    assert r.status_code == 422, r.text
    assert await _media_count(db_conn_and_sessionmaker) == 0
