"""...

Revision ID: 9594d6202a67
Revises: 
Create Date: 2025-12-29 10:31:06.381488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9594d6202a67'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


"""...

Revision ID: 9594d6202a67
Revises:
Create Date: 2025-12-29 10:31:06.381488

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9594d6202a67"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------- users ----------
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(length=40), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255), nullable=True, unique=True),
        sa.Column("display_name", sa.String(length=40), nullable=False),
        sa.Column("password", sa.String(length=128), nullable=True),
        sa.Column("role", sa.Text(), nullable=False, server_default=sa.text("'CUSTOMER'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_check_constraint(
        "users_role_check",
        "users",
        "role in ('GUEST','CUSTOMER','INSTRUCTOR','CONTENT_MANAGER','ADMIN')",
    )

    # ---------- oauth_accounts ----------
    op.create_table(
        "oauth_accounts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(length=10), nullable=False),
        sa.Column("provider_account_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("provider", "provider_account_id", name="uq_provider_provider_account_id"),
    )

    # ---------- calendars ----------
    op.create_table(
        "calendars",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("host_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("topics", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("host_id", name="uq_calendar_host_id"),
    )

    # ---------- time_slots ----------
    op.create_table(
        "time_slots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("weekdays", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("calendar_id", sa.Integer(), sa.ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_time_slots_calendar_id", "time_slots", ["calendar_id"])

    # ---------- bookings ----------
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("when", sa.Date(), nullable=False),
        sa.Column("topic", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'CONFIRMED'")),
        sa.Column("description", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("time_slot_id", sa.Integer(), sa.ForeignKey("time_slots.id", ondelete="CASCADE"), nullable=False),
        sa.Column("guest_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_bookings_guest_id", "bookings", ["guest_id"])
    op.create_index("ix_bookings_time_slot_id", "bookings", ["time_slot_id"])

    # (중요) uq_booking_active_slot_date는 bbcea 마이그레이션에서 IF NOT EXISTS로 만들고 있으니
    # 여기서는 굳이 만들지 않아도 됨. (중복 방지)
    # 대신, 모델/정책에 맞춘 status check는 넣어두는 게 안전
    op.create_check_constraint(
        "bookings_status_check",
        "bookings",
        "status in ('CONFIRMED','CANCELLED','COMPLETED')",
    )

    # ---------- instructor_staff ----------
    op.create_table(
        "instructor_staff",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("instructor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("staff_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("instructor_id", "staff_user_id", name="uq_instructor_staff_pair"),
    )
    op.create_index("ix_instructor_staff_instructor_id", "instructor_staff", ["instructor_id"])
    op.create_index("ix_instructor_staff_staff_user_id", "instructor_staff", ["staff_user_id"])


def downgrade() -> None:
    op.drop_index("ix_instructor_staff_staff_user_id", table_name="instructor_staff")
    op.drop_index("ix_instructor_staff_instructor_id", table_name="instructor_staff")
    op.drop_table("instructor_staff")

    op.drop_constraint("bookings_status_check", "bookings", type_="check")
    op.drop_index("ix_bookings_time_slot_id", table_name="bookings")
    op.drop_index("ix_bookings_guest_id", table_name="bookings")
    op.drop_table("bookings")

    op.drop_index("ix_time_slots_calendar_id", table_name="time_slots")
    op.drop_table("time_slots")

    op.drop_table("calendars")

    op.drop_table("oauth_accounts")

    op.drop_constraint("users_role_check", "users", type_="check")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
