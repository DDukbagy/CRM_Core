"""init schema tables

Revision ID: 91d68413f8d6
Revises: 41fd85a02af6
Create Date: 2026-02-22 06:20:42.037973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.base import Base
import app.db.models


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
