"""SQLAlchemy ORM models for engineering metrics database."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class DeploymentRecord(Base):
    """GitHub deployment record stored in database."""

    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_deployment_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    sha: Mapped[str] = mapped_column(String(40))
    ref: Mapped[str] = mapped_column(String(255))
    environment: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)  # success, failure, pending, in_progress
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_deployments_created_status", "created_at", "status"),
    )


class PullRequestRecord(Base):
    """GitHub pull request record stored in database."""

    __tablename__ = "pull_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    github_pr_number: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    merged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    first_commit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )


class IncidentRecord(Base):
    """Incident.io incident record stored in database."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)
    incident_io_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50))
    severity: Mapped[str] = mapped_column(String(20), index=True)  # critical, major, minor
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    impact_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    time_to_resolve_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_change_related: Mapped[bool] = mapped_column(Boolean, default=True)
    is_user_impacting: Mapped[bool] = mapped_column(Boolean, default=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_incidents_created_severity", "created_at", "severity"),
    )


class DoraMetricsSnapshot(Base):
    """Historical snapshot of calculated DORA metrics."""

    __tablename__ = "dora_metrics_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    period_type: Mapped[str] = mapped_column(String(20), index=True)  # weekly, monthly
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Deployment Frequency
    df_deployments_per_day: Mapped[float] = mapped_column(Float)
    df_deployments_per_week: Mapped[float] = mapped_column(Float)
    df_total_deployments: Mapped[int] = mapped_column(Integer)
    df_rating: Mapped[str] = mapped_column(String(20))

    # Lead Time
    lt_average_hours: Mapped[float] = mapped_column(Float)
    lt_median_hours: Mapped[float] = mapped_column(Float)
    lt_p90_hours: Mapped[float] = mapped_column(Float)
    lt_rating: Mapped[str] = mapped_column(String(20))

    # Change Failure Rate
    cfr_percentage: Mapped[float] = mapped_column(Float)
    cfr_failed_changes: Mapped[int] = mapped_column(Integer)
    cfr_total_deployments: Mapped[int] = mapped_column(Integer)
    cfr_rating: Mapped[str] = mapped_column(String(20))

    # MTTR
    mttr_average_hours: Mapped[float] = mapped_column(Float)
    mttr_median_hours: Mapped[float] = mapped_column(Float)
    mttr_incidents: Mapped[int] = mapped_column(Integer)
    mttr_rating: Mapped[str] = mapped_column(String(20))

    # Overall
    overall_rating: Mapped[str] = mapped_column(String(20))
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_snapshots_period", "period_type", "period_start"),
    )
