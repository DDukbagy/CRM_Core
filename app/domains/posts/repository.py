from typing import Optional, List
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.domains.posts.models import Post
from app.domains.posts.schemas import PostCreate

class PostRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # [수정됨] created_by_user_id 인자를 받을 수 있도록 추가했습니다.
    async def create(self, post_in: PostCreate, created_by_user_id: UUID) -> Post:
        """
        새로운 게시글을 DB에 저장합니다.
        Schema(PostCreate)의 데이터를 Model(Post)로 변환하여 저장합니다.
        """
        db_obj = Post(
            **post_in.model_dump(),
            # [중요] 전달받은 작성자 ID를 모델에 할당
            created_by_user_id=created_by_user_id
        )
        
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        
        return db_obj

    async def get_all(self, skip: int = 0, limit: int = 10) -> List[Post]:
        """
        게시글 목록을 최신순으로 조회합니다. (Admin용)
        """
        query = select(Post).order_by(desc(Post.created_at)).offset(skip).limit(limit)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_by_id(self, post_id: UUID) -> Optional[Post]:
        """
        특정 ID의 게시글을 조회합니다.
        """
        query = select(Post).where(Post.id == post_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()