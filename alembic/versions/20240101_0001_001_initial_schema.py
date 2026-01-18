"""Initial schema for engineering metrics database.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create deployments table
    op.create_table(
        "deployments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("github_deployment_id", sa.Integer(), nullable=False),
        sa.Column("sha", sa.String(length=40), nullable=False),
        sa.Column("ref", sa.String(length=255), nullable=False),
        sa.Column("environment", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_deployment_id"),
    )
    op.create_index("ix_deployments_github_deployment_id", "deployments", ["github_deployment_id"])
    op.create_index("ix_deployments_environment", "deployments", ["environment"])
    op.create_index("ix_deployments_status", "deployments", ["status"])
    op.create_index("ix_deployments_created_at", "deployments", ["created_at"])
    op.create_index("idx_deployments_created_status", "deployments", ["created_at", "status"])

    # Create pull_requests table
    op.create_table(
        "pull_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("github_pr_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("merged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_commit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("github_pr_number"),
    )
    op.create_index("ix_pull_requests_github_pr_number", "pull_requests", ["github_pr_number"])
    op.create_index("ix_pull_requests_merged_at", "pull_requests", ["merged_at"])

    # Create incidents table
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("incident_io_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("impact_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("time_to_resolve_hours", sa.Float(), nullable=True),
        sa.Column("is_change_related", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_user_impacting", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("incident_io_id"),
    )
    op.create_index("ix_incidents_incident_io_id", "incidents", ["incident_io_id"])
    op.create_index("ix_incidents_severity", "incidents", ["severity"])
    op.create_index("ix_incidents_created_at", "incidents", ["created_at"])
    op.create_index("idx_incidents_created_severity", "incidents", ["created_at", "severity"])

    # Create dora_metrics_snapshots table
    op.create_table(
        "dora_metrics_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("period_type", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        # Deployment Frequency
        sa.Column("df_deployments_per_day", sa.Float(), nullable=False),
        sa.Column("df_deployments_per_week", sa.Float(), nullable=False),
        sa.Column("df_total_deployments", sa.Integer(), nullable=False),
        sa.Column("df_rating", sa.String(length=20), nullable=False),
        # Lead Time
        sa.Column("lt_average_hours", sa.Float(), nullable=False),
        sa.Column("lt_median_hours", sa.Float(), nullable=False),
        sa.Column("lt_p90_hours", sa.Float(), nullable=False),
        sa.Column("lt_rating", sa.String(length=20), nullable=False),
        # Change Failure Rate
        sa.Column("cfr_percentage", sa.Float(), nullable=False),
        sa.Column("cfr_failed_changes", sa.Integer(), nullable=False),
        sa.Column("cfr_total_deployments", sa.Integer(), nullable=False),
        sa.Column("cfr_rating", sa.String(length=20), nullable=False),
        # MTTR
        sa.Column("mttr_average_hours", sa.Float(), nullable=False),
        sa.Column("mttr_median_hours", sa.Float(), nullable=False),
        sa.Column("mttr_incidents", sa.Integer(), nullable=False),
        sa.Column("mttr_rating", sa.String(length=20), nullable=False),
        # Overall
        sa.Column("overall_rating", sa.String(length=20), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dora_metrics_snapshots_period_type", "dora_metrics_snapshots", ["period_type"])
    op.create_index("ix_dora_metrics_snapshots_period_start", "dora_metrics_snapshots", ["period_start"])
    op.create_index("idx_snapshots_period", "dora_metrics_snapshots", ["period_type", "period_start"])


def downgrade() -> None:
    op.drop_table("dora_metrics_snapshots")
    op.drop_table("incidents")
    op.drop_table("pull_requests")
    op.drop_table("deployments")
