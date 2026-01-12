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
    """Change failure rate metric."""

    percentage: float
    failed_deployments: int
    total_deployments: int
    rating: DoraRating


class MTTR(BaseModel):
    """Mean time to recovery metric."""

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


class LinearIssue(BaseModel):
    """Linear issue data."""

    id: str
    identifier: str
    title: str
    state: str
    created_at: datetime
    completed_at: datetime | None = None
    started_at: datetime | None = None
    cycle_time_hours: float | None = None
    labels: list[str] = Field(default_factory=list)


class SlabPostmortem(BaseModel):
    """Slab postmortem data."""

    id: str
    title: str
    incident_date: datetime
    resolved_at: datetime
    severity: Literal["critical", "major", "minor"]
    time_to_resolve_hours: float


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
    incidents: list[LinearIssue] = Field(default_factory=list)
    postmortems: list[SlabPostmortem] = Field(default_factory=list)
