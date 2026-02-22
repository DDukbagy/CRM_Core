"""init schema tables

Revision ID: 91d68413f8d6
Revises: e5278775d3fc
Create Date: 2026-02-22 06:20:42.037973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from app.db.base import Base


# revision identifiers, used by Alembic.
revision: str = '91d68413f8d6'
down_revision: Union[str, Sequence[str], None] = '41fd85a02af6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    Base.metadata.create_all(bind)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    Base.metadata.drop_all(bind)
