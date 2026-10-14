"""persist incident-linked automatic recovery outcomes

Revision ID: ab34cd56ef78
Revises: f24c9a67d831
Create Date: 2026-10-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "ab34cd56ef78"
down_revision = "f24c9a67d831"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("recovery_jobs_backup_id_fkey", "recovery_jobs", type_="foreignkey")
    op.alter_column("recovery_jobs", "backup_id", existing_type=sa.Uuid(), nullable=True)
    op.create_foreign_key(
        "recovery_jobs_backup_id_fkey",
        "recovery_jobs",
        "backup_snapshots",
        ["backup_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("recovery_jobs", sa.Column("security_event_id", sa.Uuid(), nullable=True))
    op.add_column("recovery_jobs", sa.Column("device_id", sa.Uuid(), nullable=True))
    op.add_column("recovery_jobs", sa.Column("source_directory", sa.Text(), nullable=True))
    op.alter_column("recovery_jobs", "recovery_directory", existing_type=sa.Text(), nullable=True)
    op.create_foreign_key(
        "fk_recovery_jobs_security_event_id_security_events",
        "recovery_jobs",
        "security_events",
        ["security_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_recovery_jobs_device_id_devices",
        "recovery_jobs",
        "devices",
        ["device_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_recovery_jobs_security_event_id", "recovery_jobs", ["security_event_id"], unique=True)
    op.create_index("ix_recovery_jobs_device_id", "recovery_jobs", ["device_id"])
    op.create_index(
        "uq_recovery_jobs_active_source",
        "recovery_jobs",
        ["source_directory"],
        unique=True,
        postgresql_where=sa.text("source_directory IS NOT NULL AND status IN ('QUEUED', 'RUNNING')"),
        sqlite_where=sa.text("source_directory IS NOT NULL AND status IN ('QUEUED', 'RUNNING')"),
    )


def downgrade() -> None:
    op.drop_index("uq_recovery_jobs_active_source", table_name="recovery_jobs")
    op.drop_index("ix_recovery_jobs_device_id", table_name="recovery_jobs")
    op.drop_index("ix_recovery_jobs_security_event_id", table_name="recovery_jobs")
    op.drop_constraint("fk_recovery_jobs_device_id_devices", "recovery_jobs", type_="foreignkey")
    op.drop_constraint(
        "fk_recovery_jobs_security_event_id_security_events",
        "recovery_jobs",
        type_="foreignkey",
    )
    op.drop_column("recovery_jobs", "source_directory")
    op.drop_column("recovery_jobs", "device_id")
    op.drop_column("recovery_jobs", "security_event_id")
    op.alter_column("recovery_jobs", "recovery_directory", existing_type=sa.Text(), nullable=False)
    op.drop_constraint("recovery_jobs_backup_id_fkey", "recovery_jobs", type_="foreignkey")
    op.alter_column("recovery_jobs", "backup_id", existing_type=sa.Uuid(), nullable=False)
    op.create_foreign_key(
        "recovery_jobs_backup_id_fkey",
        "recovery_jobs",
        "backup_snapshots",
        ["backup_id"],
        ["id"],
        ondelete="CASCADE",
    )
