"""associate scheduled snapshots with their registered device

Revision ID: f24c9a67d831
Revises: e8c1a7409b23
Create Date: 2026-10-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f24c9a67d831"
down_revision = "e8c1a7409b23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "backup_snapshots",
        sa.Column("device_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_backup_snapshots_device_id_devices",
        "backup_snapshots",
        "devices",
        ["device_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_backup_snapshots_device_id",
        "backup_snapshots",
        ["device_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_backup_snapshots_device_id", table_name="backup_snapshots")
    op.drop_constraint(
        "fk_backup_snapshots_device_id_devices",
        "backup_snapshots",
        type_="foreignkey",
    )
    op.drop_column("backup_snapshots", "device_id")
