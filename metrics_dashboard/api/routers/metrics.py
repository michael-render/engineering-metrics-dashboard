"""Metrics API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from metrics_dashboard.api.schemas import (
    ChangeFailureRateResponse,
    DeploymentFrequencyResponse,
    LeadTimeResponse,
    MetricsResponse,
    MetricsSnapshotResponse,
    MTTRResponse,
    PeriodResponse,
    TrendDataPoint,
    TrendsResponse,
    TrendSummary,
)
from metrics_dashboard.database.models import DoraMetricsSnapshot
from metrics_dashboard.database.repository import MetricsRepository
from metrics_dashboard.database.session import get_session_dependency

router = APIRouter()


def _snapshot_to_response(snapshot: DoraMetricsSnapshot) -> MetricsSnapshotResponse:
    """Convert database snapshot to API response."""
    return MetricsSnapshotResponse(
        period=PeriodResponse(
            type=snapshot.period_type,  # type: ignore
            start_date=snapshot.period_start,
            end_date=snapshot.period_end,
        ),
        metrics=MetricsResponse(
            deployment_frequency=DeploymentFrequencyResponse(
                deployments_per_day=snapshot.df_deployments_per_day,
                deployments_per_week=snapshot.df_deployments_per_week,
                total_deployments=snapshot.df_total_deployments,
                rating=snapshot.df_rating,
            ),
            lead_time=LeadTimeResponse(
                average_hours=snapshot.lt_average_hours,
                median_hours=snapshot.lt_median_hours,
                p90_hours=snapshot.lt_p90_hours,
                rating=snapshot.lt_rating,
            ),
            change_failure_rate=ChangeFailureRateResponse(
                percentage=snapshot.cfr_percentage,
                failed_changes=snapshot.cfr_failed_changes,
                total_deployments=snapshot.cfr_total_deployments,
                rating=snapshot.cfr_rating,
            ),
            mttr=MTTRResponse(
                average_hours=snapshot.mttr_average_hours,
                median_hours=snapshot.mttr_median_hours,
                incidents=snapshot.mttr_incidents,
                rating=snapshot.mttr_rating,
            ),
        ),
        overall_rating=snapshot.overall_rating,
        generated_at=snapshot.generated_at,
    )


@router.get("/latest", response_model=MetricsSnapshotResponse)
async def get_latest_metrics(
    period_type: str | None = Query(None, description="Filter by period type (weekly/monthly)"),
    session: AsyncSession = Depends(get_session_dependency),
) -> MetricsSnapshotResponse:
    """Get the most recent metrics snapshot."""
    repo = MetricsRepository(session)
    snapshot = await repo.get_latest_snapshot(period_type)

    if not snapshot:
        raise HTTPException(status_code=404, detail="No metrics snapshots found")

    return _snapshot_to_response(snapshot)


@router.get("", response_model=MetricsSnapshotResponse)
async def get_metrics_by_range(
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    period_type: str | None = Query(None, description="Filter by period type (weekly/monthly)"),
    session: AsyncSession = Depends(get_session_dependency),
) -> MetricsSnapshotResponse:
    """Get metrics for a specific date range.

    Returns the most recent snapshot that falls within the specified range.
    """
    repo = MetricsRepository(session)
    snapshots = await repo.get_snapshots_in_range(start_date, end_date, period_type)

    if not snapshots:
        raise HTTPException(
            status_code=404,
            detail=f"No metrics found for period {start_date.date()} to {end_date.date()}",
        )

    # Return the most recent snapshot in the range
    return _snapshot_to_response(snapshots[-1])


@router.get("/trends", response_model=TrendsResponse)
async def get_metrics_trends(
    periods: int = Query(12, ge=1, le=52, description="Number of periods to return"),
    period_type: str = Query("weekly", description="Period type (weekly/monthly)"),
    session: AsyncSession = Depends(get_session_dependency),
) -> TrendsResponse:
    """Get historical metrics for trend analysis."""
    repo = MetricsRepository(session)
    snapshots = await repo.get_recent_snapshots(periods, period_type)

    if not snapshots:
        raise HTTPException(status_code=404, detail="No metrics snapshots found")

    # Convert snapshots to trend data points
    trends = [
        TrendDataPoint(
            period_start=s.period_start,
            period_end=s.period_end,
            deployment_frequency=s.df_deployments_per_day,
            lead_time_hours=s.lt_median_hours,
            change_failure_rate=s.cfr_percentage,
            mttr_hours=s.mttr_median_hours,
            overall_rating=s.overall_rating,
        )
        for s in snapshots
    ]

    # Calculate summary statistics
    if len(trends) >= 2:
        avg_df = sum(t.deployment_frequency for t in trends) / len(trends)
        avg_lt = sum(t.lead_time_hours for t in trends) / len(trends)
        avg_cfr = sum(t.change_failure_rate for t in trends) / len(trends)
        avg_mttr = sum(t.mttr_hours for t in trends) / len(trends)

        # Determine trend direction based on recent vs older data
        mid = len(trends) // 2
        recent_avg = sum(t.deployment_frequency for t in trends[mid:]) / len(trends[mid:])
        older_avg = sum(t.deployment_frequency for t in trends[:mid]) / len(trends[:mid])

        if recent_avg > older_avg * 1.1:
            trend_direction = "improving"
        elif recent_avg < older_avg * 0.9:
            trend_direction = "declining"
        else:
            trend_direction = "stable"
    else:
        avg_df = trends[0].deployment_frequency if trends else 0
        avg_lt = trends[0].lead_time_hours if trends else 0
        avg_cfr = trends[0].change_failure_rate if trends else 0
        avg_mttr = trends[0].mttr_hours if trends else 0
        trend_direction = "stable"

    return TrendsResponse(
        period_type=period_type,
        trends=trends,
        summary=TrendSummary(
            avg_deployment_frequency=avg_df,
            avg_lead_time=avg_lt,
            avg_cfr=avg_cfr,
            avg_mttr=avg_mttr,
            trend_direction=trend_direction,  # type: ignore
        ),
    )
