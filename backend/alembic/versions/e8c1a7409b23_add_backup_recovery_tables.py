"""add backup and recovery tables

Revision ID: e8c1a7409b23
Revises: c1d2e3f4b5a6
Create Date: 2026-10-12 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e8c1a7409b23"
down_revision = ("c1d2e3f4b5a6", "252f23614acf")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_directory", sa.Text(), nullable=False),
        sa.Column("destination_directory", sa.Text(), nullable=False),
        sa.Column("snapshot_directory", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "QUEUED",
                "RUNNING",
                "VERIFYING",
                "VERIFIED",
                "FAILED",
                "CORRUPT",
                name="backupstatus",
                native_enum=False,
            ),
            server_default="QUEUED",
            nullable=False,
        ),
        sa.Column("manifest", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_snapshots_user_id", "backup_snapshots", ["user_id"])
    op.create_index("ix_backup_snapshots_status", "backup_snapshots", ["status"])

    op.create_table(
        "recovery_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("backup_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("recovery_directory", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("QUEUED", "RUNNING", "COMPLETED", "FAILED", name="recoverystatus", native_enum=False),
            server_default="QUEUED",
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["backup_id"], ["backup_snapshots.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recovery_jobs_backup_id", "recovery_jobs", ["backup_id"])
    op.create_index("ix_recovery_jobs_user_id", "recovery_jobs", ["user_id"])
    op.create_index("ix_recovery_jobs_status", "recovery_jobs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_recovery_jobs_status", table_name="recovery_jobs")
    op.drop_index("ix_recovery_jobs_user_id", table_name="recovery_jobs")
    op.drop_index("ix_recovery_jobs_backup_id", table_name="recovery_jobs")
    op.drop_table("recovery_jobs")
    op.drop_index("ix_backup_snapshots_status", table_name="backup_snapshots")
    op.drop_index("ix_backup_snapshots_user_id", table_name="backup_snapshots")
    op.drop_table("backup_snapshots")
