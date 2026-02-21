"""booking cancel_reason, time_slot is_active, calendar_blocks

Revision ID: e5278775d3fc
Revises: 5cc9b860b849
Create Date: 2026-02-21 05:41:12.498496

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5278775d3fc'
down_revision: Union[str, Sequence[str], None] = '5cc9b860b849'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(table_name: str, schema: str = "public") -> set[str]:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = insp.get_columns(table_name, schema=schema)
    return {c["name"] for c in cols}


def upgrade() -> None:
    """Upgrade schema."""
    # 1) bookings.cancel_reason (nullable)
    bookings_cols = _column_names("bookings")
    if "cancel_reason" not in bookings_cols:
        op.add_column("bookings", sa.Column("cancel_reason", sa.Text(), nullable=True))

    # 2) time_slots.is_active (default true, not null)
    time_slots_cols = _column_names("time_slots")
    if "is_active" not in time_slots_cols:
        # 안전하게: nullable True로 추가 → 기존 row 채움 → not null로 변경
        op.add_column(
            "time_slots",
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=True),
        )
        op.execute("UPDATE time_slots SET is_active = TRUE WHERE is_active IS NULL")
        op.alter_column("time_slots", "is_active", nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    time_slots_cols = _column_names("time_slots")
    if "is_active" in time_slots_cols:
        op.drop_column("time_slots", "is_active")

    bookings_cols = _column_names("bookings")
    if "cancel_reason" in bookings_cols:
        op.drop_column("bookings", "cancel_reason")
        