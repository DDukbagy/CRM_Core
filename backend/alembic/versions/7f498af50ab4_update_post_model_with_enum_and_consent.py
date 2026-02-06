"""update post model with enum and consent

Revision ID: 7f498af50ab4
Revises: 748ea71fe207
Create Date: 2026-01-31 02:52:59.154768

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '7f498af50ab4'
down_revision: Union[str, Sequence[str], None] = '748ea71fe207'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Enum 타입 안전 생성 (Raw SQL)
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'posttype') THEN CREATE TYPE posttype AS ENUM ('NOTICE', 'COMMUNITY', 'FEEDBACK'); END IF; END $$;")
    op.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'poststatus') THEN CREATE TYPE poststatus AS ENUM ('PUBLIC', 'MEMBERS', 'PRIVATE'); END IF; END $$;")

    # 2. 신규 컬럼 추가 (status 제외)
    op.add_column('posts', sa.Column('title', sa.String(), nullable=True))
    op.add_column('posts', sa.Column('post_type', sa.Enum('NOTICE', 'COMMUNITY', 'FEEDBACK', name='posttype'), nullable=False, server_default='COMMUNITY'))
    op.add_column('posts', sa.Column('is_consent_given', sa.Boolean(), nullable=False, server_default='false'))

    # 3. status 컬럼 교체 (기존 컬럼 삭제 -> 새 컬럼 생성)
    # 3-1. 임시 컬럼(status_new) 생성
    op.add_column('posts', sa.Column('status_new', sa.Enum('PUBLIC', 'MEMBERS', 'PRIVATE', name='poststatus'), nullable=True))
    
    # 3-2. 데이터 이관 (Text -> Enum 변환)
    # upper(status)를 사용해 소문자/대문자 이슈 방지
    op.execute("UPDATE posts SET status_new = upper(status)::poststatus")
    
    # 3-3. 데이터가 비어있을 경우 기본값 'PRIVATE'로 채움 (안전장치)
    op.execute("UPDATE posts SET status_new = 'PRIVATE'::poststatus WHERE status_new IS NULL")
    
    # 3-4. Nullable=False 설정
    op.alter_column('posts', 'status_new', nullable=False)

    # 3-5. 기존 status 컬럼 삭제 (충돌 원인 제거)
    op.drop_column('posts', 'status')

    # 3-6. 임시 컬럼 이름 변경 (status_new -> status)
    op.alter_column('posts', 'status_new', new_column_name='status')
    
    # 3-7. 기본값 설정
    op.execute("ALTER TABLE posts ALTER COLUMN status SET DEFAULT 'PRIVATE'::poststatus")

    # 4. caption 타입 변경
    op.alter_column('posts', 'caption',
               existing_type=sa.TEXT(),
               type_=sa.String(),
               existing_nullable=True)
               
    # 5. 인덱스 생성
    op.create_index(op.f('ix_posts_instructor_id'), 'posts', ['instructor_id'], unique=False)
    op.create_index(op.f('ix_posts_owner_user_id'), 'posts', ['owner_user_id'], unique=False)
    op.create_index(op.f('ix_posts_post_type'), 'posts', ['post_type'], unique=False)
    op.create_index(op.f('ix_posts_status'), 'posts', ['status'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_posts_status'), table_name='posts')
    op.drop_index(op.f('ix_posts_post_type'), table_name='posts')
    op.drop_index(op.f('ix_posts_owner_user_id'), table_name='posts')
    op.drop_index(op.f('ix_posts_instructor_id'), table_name='posts')
    
    op.alter_column('posts', 'caption',
               existing_type=sqlmodel.sql.sqltypes.AutoString(),
               type_=sa.TEXT(),
               existing_nullable=True)
               
    op.alter_column('posts', 'status',
               existing_type=sa.Enum('PUBLIC', 'MEMBERS', 'PRIVATE', name='poststatus'),
               type_=sa.TEXT(),
               existing_nullable=False)
               
    op.drop_column('posts', 'is_consent_given')
    op.drop_column('posts', 'post_type')
    op.drop_column('posts', 'title')

    sa.Enum(name='posttype').drop(op.get_bind())
    sa.Enum(name='poststatus').drop(op.get_bind())
    # ### end Alembic commands ###
