"""API response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PeriodResponse(BaseModel):
    """Period information in API responses."""

    type: Literal["weekly", "monthly"]
    start_date: datetime
    end_date: datetime


class DeploymentFrequencyResponse(BaseModel):
    """Deployment frequency metric response."""

    deployments_per_day: float
    deployments_per_week: float
    total_deployments: int
    rating: str


class LeadTimeResponse(BaseModel):
    """Lead time metric response."""

    average_hours: float
    median_hours: float
    p90_hours: float
    rating: str


class ChangeFailureRateResponse(BaseModel):
    """Change failure rate metric response."""

    percentage: float
    failed_changes: int
    total_deployments: int
    rating: str


class MTTRResponse(BaseModel):
    """MTTR metric response."""

    average_hours: float
    median_hours: float
    incidents: int
    rating: str


class MetricsResponse(BaseModel):
    """Full DORA metrics response."""

    deployment_frequency: DeploymentFrequencyResponse
    lead_time: LeadTimeResponse
    change_failure_rate: ChangeFailureRateResponse
    mttr: MTTRResponse


class MetricsSnapshotResponse(BaseModel):
    """Complete metrics snapshot response."""

    period: PeriodResponse
    metrics: MetricsResponse
    overall_rating: str
    generated_at: datetime


class TrendDataPoint(BaseModel):
    """Single data point in a trend."""

    period_start: datetime
    period_end: datetime
    deployment_frequency: float
    lead_time_hours: float
    change_failure_rate: float
    mttr_hours: float
    overall_rating: str


class TrendSummary(BaseModel):
    """Summary statistics for trends."""

    avg_deployment_frequency: float
    avg_lead_time: float
    avg_cfr: float
    avg_mttr: float
    trend_direction: Literal["improving", "stable", "declining"]


class TrendsResponse(BaseModel):
    """Trends API response."""

    period_type: str
    trends: list[TrendDataPoint]
    summary: TrendSummary


class DeploymentResponse(BaseModel):
    """Deployment record response."""

    github_deployment_id: int
    sha: str
    ref: str
    environment: str
    status: str
    created_at: datetime


class IncidentResponse(BaseModel):
    """Incident record response."""

    incident_io_id: str
    name: str
    status: str
    severity: str
    created_at: datetime
    resolved_at: datetime | None
    time_to_resolve_hours: float | None
    is_change_related: bool
    is_user_impacting: bool
