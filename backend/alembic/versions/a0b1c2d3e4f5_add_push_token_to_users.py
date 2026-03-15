"""add push_token to users

Revision ID: a0b1c2d3e4f5
Revises: f8a9b0c1d2e3
Create Date: 2026-03-12

변경 내용:
- users.push_token VARCHAR(200) NULL 추가 (Expo Push Token 저장용)
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a0b1c2d3e4f5"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS push_token VARCHAR(200)"
    ))


def downgrade() -> None:
    op.drop_column("users", "push_token")
