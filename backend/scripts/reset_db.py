import asyncio
from sqlalchemy import text
from sqlmodel import SQLModel
from app.db.session import engine

# SQLModel이 테이블 구조를 알 수 있도록 모델들을 가져옵니다.
from app.domains.posts.models import Post, Comment, PostLike, PostMedia, Notification

async def reset_db():
    print("🔄 Comments 테이블 초기화 중...")
    
    # 1. 기존 테이블 삭제 (CASCADE로 연관 데이터까지 정리)
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS comments CASCADE;"))

    # 2. 테이블 재생성 (수정된 모델 반영)
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        print("✨ 초기화 완료. (parent_id 컬럼 생성됨)")

if __name__ == "__main__":
    asyncio.run(reset_db())