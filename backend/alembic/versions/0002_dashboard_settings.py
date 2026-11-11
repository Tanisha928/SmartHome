"""Add persisted per-user dashboard settings.

Revision ID: 0002_dashboard_settings
Revises: 0001_initial
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_dashboard_settings"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dashboard_settings",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("default_map_latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("default_map_longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("show_critical_toasts", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("play_alert_sound", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"]),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("dashboard_settings")
