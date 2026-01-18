"""Repository layer for database operations."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from metrics_dashboard.database.models import (
    DeploymentRecord,
    DoraMetricsSnapshot,
    IncidentRecord,
    PullRequestRecord,
)
from metrics_dashboard.dora import get_overall_rating
from metrics_dashboard.models import DoraMetrics, MetricsPeriod


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    """Parse datetime from string or return as-is if already datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    # Handle ISO format strings (e.g., '2026-01-08T19:08:28Z')
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class DataRepository:
    """Repository for raw data operations (deployments, PRs, incidents)."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_deployments(self, deployments: list[dict]) -> int:
        """Upsert deployment records.

        Returns the number of records processed.
        """
        if not deployments:
            return 0

        for dep in deployments:
            stmt = insert(DeploymentRecord).values(
                github_deployment_id=dep["id"],
                sha=dep["sha"],
                ref=dep["ref"],
                environment=dep["environment"],
                status=dep["status"],
                created_at=_parse_datetime(dep["created_at"]),
                fetched_at=datetime.utcnow(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["github_deployment_id"],
                set_={
                    "status": stmt.excluded.status,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            await self.session.execute(stmt)

        return len(deployments)

    async def upsert_pull_requests(self, pull_requests: list[dict]) -> int:
        """Upsert pull request records.

        Returns the number of records processed.
        """
        if not pull_requests:
            return 0

        for pr in pull_requests:
            stmt = insert(PullRequestRecord).values(
                github_pr_number=pr["number"],
                title=pr["title"],
                created_at=_parse_datetime(pr["created_at"]),
                merged_at=_parse_datetime(pr.get("merged_at")),
                first_commit_at=_parse_datetime(pr.get("first_commit_at")),
                fetched_at=datetime.utcnow(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["github_pr_number"],
                set_={
                    "title": stmt.excluded.title,
                    "merged_at": stmt.excluded.merged_at,
                    "first_commit_at": stmt.excluded.first_commit_at,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            await self.session.execute(stmt)

        return len(pull_requests)

    async def upsert_incidents(self, incidents: list[dict]) -> int:
        """Upsert incident records.

        Returns the number of records processed.
        """
        if not incidents:
            return 0

        for inc in incidents:
            stmt = insert(IncidentRecord).values(
                incident_io_id=inc["id"],
                name=inc["name"],
                status=inc["status"],
                severity=inc["severity"],
                created_at=_parse_datetime(inc["created_at"]),
                resolved_at=_parse_datetime(inc.get("resolved_at")),
                impact_started_at=_parse_datetime(inc.get("impact_started_at")),
                duration_seconds=inc.get("duration_seconds"),
                time_to_resolve_hours=inc.get("time_to_resolve_hours"),
                is_change_related=inc.get("is_change_related", True),
                is_user_impacting=inc.get("is_user_impacting", True),
                fetched_at=datetime.utcnow(),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["incident_io_id"],
                set_={
                    "name": stmt.excluded.name,
                    "status": stmt.excluded.status,
                    "severity": stmt.excluded.severity,
                    "resolved_at": stmt.excluded.resolved_at,
                    "impact_started_at": stmt.excluded.impact_started_at,
                    "duration_seconds": stmt.excluded.duration_seconds,
                    "time_to_resolve_hours": stmt.excluded.time_to_resolve_hours,
                    "is_change_related": stmt.excluded.is_change_related,
                    "is_user_impacting": stmt.excluded.is_user_impacting,
                    "fetched_at": stmt.excluded.fetched_at,
                },
            )
            await self.session.execute(stmt)

        return len(incidents)

    async def get_deployments_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
        status: str | None = None,
        limit: int = 100,
    ) -> list[DeploymentRecord]:
        """Get deployments within a date range."""
        query = select(DeploymentRecord).where(
            DeploymentRecord.created_at >= start_date,
            DeploymentRecord.created_at <= end_date,
        )
        if status:
            query = query.where(DeploymentRecord.status == status)
        query = query.order_by(DeploymentRecord.created_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_incidents_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[IncidentRecord]:
        """Get incidents within a date range."""
        query = select(IncidentRecord).where(
            IncidentRecord.created_at >= start_date,
            IncidentRecord.created_at <= end_date,
        )
        if severity:
            query = query.where(IncidentRecord.severity == severity)
        query = query.order_by(IncidentRecord.created_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return list(result.scalars().all())


class MetricsRepository:
    """Repository for DORA metrics snapshots."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_snapshot(self, metrics: DoraMetrics, period: MetricsPeriod) -> int:
        """Create a new metrics snapshot.

        Returns the snapshot ID.
        """
        overall = get_overall_rating(metrics)

        snapshot = DoraMetricsSnapshot(
            period_type=period.type,
            period_start=period.start_date,
            period_end=period.end_date,
            # Deployment Frequency
            df_deployments_per_day=metrics.deployment_frequency.deployments_per_day,
            df_deployments_per_week=metrics.deployment_frequency.deployments_per_week,
            df_total_deployments=metrics.deployment_frequency.total_deployments,
            df_rating=metrics.deployment_frequency.rating.value,
            # Lead Time
            lt_average_hours=metrics.lead_time.average_hours,
            lt_median_hours=metrics.lead_time.median_hours,
            lt_p90_hours=metrics.lead_time.p90_hours,
            lt_rating=metrics.lead_time.rating.value,
            # Change Failure Rate
            cfr_percentage=metrics.change_failure_rate.percentage,
            cfr_failed_changes=metrics.change_failure_rate.failed_changes,
            cfr_total_deployments=metrics.change_failure_rate.total_deployments,
            cfr_rating=metrics.change_failure_rate.rating.value,
            # MTTR
            mttr_average_hours=metrics.mttr.average_hours,
            mttr_median_hours=metrics.mttr.median_hours,
            mttr_incidents=metrics.mttr.incidents,
            mttr_rating=metrics.mttr.rating.value,
            # Overall
            overall_rating=overall.value,
            generated_at=datetime.utcnow(),
        )

        self.session.add(snapshot)
        await self.session.flush()
        return snapshot.id

    async def get_latest_snapshot(self, period_type: str | None = None) -> DoraMetricsSnapshot | None:
        """Get the most recent metrics snapshot."""
        query = select(DoraMetricsSnapshot).order_by(DoraMetricsSnapshot.generated_at.desc())
        if period_type:
            query = query.where(DoraMetricsSnapshot.period_type == period_type)
        query = query.limit(1)

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_snapshots_in_range(
        self,
        start_date: datetime,
        end_date: datetime,
        period_type: str | None = None,
    ) -> list[DoraMetricsSnapshot]:
        """Get all snapshots within a date range."""
        query = select(DoraMetricsSnapshot).where(
            DoraMetricsSnapshot.period_start >= start_date,
            DoraMetricsSnapshot.period_end <= end_date,
        )
        if period_type:
            query = query.where(DoraMetricsSnapshot.period_type == period_type)
        query = query.order_by(DoraMetricsSnapshot.period_start.asc())

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent_snapshots(
        self,
        periods: int = 12,
        period_type: str = "weekly",
    ) -> list[DoraMetricsSnapshot]:
        """Get the most recent N snapshots for trend analysis."""
        query = (
            select(DoraMetricsSnapshot)
            .where(DoraMetricsSnapshot.period_type == period_type)
            .order_by(DoraMetricsSnapshot.period_start.desc())
            .limit(periods)
        )

        result = await self.session.execute(query)
        snapshots = list(result.scalars().all())
        # Return in chronological order
        return list(reversed(snapshots))
