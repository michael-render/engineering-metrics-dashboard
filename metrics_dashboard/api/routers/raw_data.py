"""Raw data API endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from metrics_dashboard.api.schemas import DeploymentResponse, IncidentResponse
from metrics_dashboard.database.repository import DataRepository
from metrics_dashboard.database.session import get_session_dependency

router = APIRouter()


@router.get("/deployments", response_model=list[DeploymentResponse])
async def get_deployments(
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    status: str | None = Query(None, description="Filter by status (success/failure/pending/in_progress)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    session: AsyncSession = Depends(get_session_dependency),
) -> list[DeploymentResponse]:
    """Get raw deployment data within a date range."""
    repo = DataRepository(session)
    deployments = await repo.get_deployments_in_range(start_date, end_date, status, limit)

    return [
        DeploymentResponse(
            github_deployment_id=d.github_deployment_id,
            sha=d.sha,
            ref=d.ref,
            environment=d.environment,
            status=d.status,
            created_at=d.created_at,
        )
        for d in deployments
    ]


@router.get("/incidents", response_model=list[IncidentResponse])
async def get_incidents(
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    severity: str | None = Query(None, description="Filter by severity (critical/major/minor)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    session: AsyncSession = Depends(get_session_dependency),
) -> list[IncidentResponse]:
    """Get raw incident data within a date range."""
    repo = DataRepository(session)
    incidents = await repo.get_incidents_in_range(start_date, end_date, severity, limit)

    return [
        IncidentResponse(
            incident_io_id=i.incident_io_id,
            name=i.name,
            status=i.status,
            severity=i.severity,
            created_at=i.created_at,
            resolved_at=i.resolved_at,
            time_to_resolve_hours=i.time_to_resolve_hours,
            is_change_related=i.is_change_related,
            is_user_impacting=i.is_user_impacting,
        )
        for i in incidents
    ]
