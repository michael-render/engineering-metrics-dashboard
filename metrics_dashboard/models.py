"""Data models for engineering metrics."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class DoraRating(str, Enum):
    """DORA performance rating levels."""

    ELITE = "elite"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MetricsPeriod(BaseModel):
    """Time period for metrics calculation."""

    type: Literal["weekly", "monthly"]
    start_date: datetime
    end_date: datetime


class DeploymentFrequency(BaseModel):
    """Deployment frequency metric."""

    deployments_per_day: float
    deployments_per_week: float
    total_deployments: int
    rating: DoraRating


class LeadTime(BaseModel):
    """Lead time for changes metric."""

    average_hours: float
    median_hours: float
    p90_hours: float
    rating: DoraRating


class ChangeFailureRate(BaseModel):
    """Change failure rate metric.

    Per DORA: The percentage of deployments causing a failure in production
    that requires remediation (e.g., rollback, hotfix, patch).
    """

    percentage: float
    failed_changes: int  # Number of deployments that caused incidents
    total_deployments: int
    rating: DoraRating


class MTTR(BaseModel):
    """Mean time to recovery metric.

    Per DORA: How long it takes to restore service when a service incident
    or a defect that impacts users occurs.
    """

    average_hours: float
    median_hours: float
    incidents: int
    rating: DoraRating


class DoraMetrics(BaseModel):
    """Complete DORA metrics."""

    deployment_frequency: DeploymentFrequency
    lead_time: LeadTime
    change_failure_rate: ChangeFailureRate
    mttr: MTTR
    period: MetricsPeriod
    generated_at: datetime = Field(default_factory=datetime.now)


class GitHubDeployment(BaseModel):
    """GitHub deployment data."""

    id: int
    sha: str
    ref: str
    environment: str
    created_at: datetime
    status: Literal["success", "failure", "pending", "in_progress"]


class GitHubPullRequest(BaseModel):
    """GitHub pull request data."""

    number: int
    title: str
    created_at: datetime
    merged_at: datetime | None = None
    first_commit_at: datetime | None = None


class Incident(BaseModel):
    """Incident from incident.io.

    Used for Change Failure Rate and MTTR calculations.
    Only change-related incidents count toward DORA metrics.

    For MTTR calculation per DORA definition ("time to restore service when
    an incident impacts users"), we prioritize:
    1. duration_seconds from incident.io's duration_metrics (most accurate)
    2. resolved_at - impact_started_at (if custom timestamp exists)
    3. resolved_at - created_at (fallback)
    """

    id: str
    name: str
    status: str  # e.g., "open", "closed", "resolved"
    severity: Literal["critical", "major", "minor"]
    created_at: datetime
    resolved_at: datetime | None = None
    impact_started_at: datetime | None = None  # From incident_timestamp_values
    duration_seconds: float | None = None  # From duration_metrics (pre-calculated MTTR)
    time_to_resolve_hours: float | None = None  # Calculated recovery time
    is_change_related: bool = True  # True if caused by a deployment/change
    is_user_impacting: bool = True  # True if incident impacted users


class MetricsReport(BaseModel):
    """Generated metrics report."""

    title: str
    period: MetricsPeriod
    metrics: DoraMetrics
    highlights: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class DataFetchResult(BaseModel):
    """Result from data source fetching."""

    deployments: list[GitHubDeployment] = Field(default_factory=list)
    pull_requests: list[GitHubPullRequest] = Field(default_factory=list)
    incidents: list[Incident] = Field(default_factory=list)  # From incident.io
