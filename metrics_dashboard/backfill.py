"""Backfill historical metrics data."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

from metrics_dashboard.clients import (
    create_github_client,
    create_incident_io_client,
)
from metrics_dashboard.database.repository import DataRepository, MetricsRepository
from metrics_dashboard.database.session import get_async_session
from metrics_dashboard.dora import calculate_dora_metrics
from metrics_dashboard.models import (
    DataFetchResult,
    GitHubDeployment,
    GitHubPullRequest,
    Incident,
    MetricsPeriod,
)


def generate_periods(
    start_date: datetime,
    end_date: datetime,
    period_type: str = "weekly",
) -> list[MetricsPeriod]:
    """Generate all periods between start and end dates."""
    periods: list[MetricsPeriod] = []
    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    end = end_date.replace(hour=23, minute=59, second=59, microsecond=0, tzinfo=timezone.utc)

    if period_type == "weekly":
        # Align to Monday
        days_since_monday = current.weekday()
        current = current - timedelta(days=days_since_monday)

        while current < end:
            period_end = current + timedelta(days=6, hours=23, minutes=59, seconds=59)
            if period_end > end:
                break
            periods.append(MetricsPeriod(
                type="weekly",
                start_date=current,
                end_date=period_end,
            ))
            current = current + timedelta(days=7)
    else:  # monthly
        # Align to first of month
        current = current.replace(day=1)

        while current < end:
            # Get last day of month
            if current.month == 12:
                next_month = current.replace(year=current.year + 1, month=1)
            else:
                next_month = current.replace(month=current.month + 1)
            period_end = next_month - timedelta(seconds=1)

            if period_end > end:
                break

            periods.append(MetricsPeriod(
                type="monthly",
                start_date=current,
                end_date=period_end,
            ))
            current = next_month

    return periods


async def backfill_period(
    period: MetricsPeriod,
    delay_seconds: float = 2.0,
) -> dict:
    """Fetch and store data for a single period.

    Returns summary of what was stored.
    """
    print(f"[Backfill] Processing {period.type} period: {period.start_date.date()} to {period.end_date.date()}")

    github_client = create_github_client()
    incident_client = create_incident_io_client()

    # Fetch deployments
    repos = await github_client.get_repos()
    all_deployments: list[GitHubDeployment] = []
    for repo in repos:
        try:
            deps = await github_client.get_deployments(repo, period)
            all_deployments.extend(deps)
            await asyncio.sleep(delay_seconds)  # Rate limit
        except Exception as e:
            print(f"[Backfill] Warning: Failed to fetch deployments for {repo}: {e}")

    # Fetch PRs
    all_prs: list[GitHubPullRequest] = []
    for repo in repos:
        try:
            prs = await github_client.get_pull_requests(repo, period)
            all_prs.extend(prs)
            await asyncio.sleep(delay_seconds)  # Rate limit
        except Exception as e:
            print(f"[Backfill] Warning: Failed to fetch PRs for {repo}: {e}")

    # Fetch incidents
    all_incidents: list[Incident] = []
    if incident_client:
        try:
            all_incidents = await incident_client.get_dora_incidents(period)
        except Exception as e:
            print(f"[Backfill] Warning: Failed to fetch incidents: {e}")

    # Store raw data
    async with get_async_session() as session:
        data_repo = DataRepository(session)
        metrics_repo = MetricsRepository(session)

        deployments_json = [d.model_dump(mode="json") for d in all_deployments]
        prs_json = [pr.model_dump(mode="json") for pr in all_prs]
        incidents_json = [inc.model_dump(mode="json") for inc in all_incidents]

        dep_count = await data_repo.upsert_deployments(deployments_json)
        pr_count = await data_repo.upsert_pull_requests(prs_json)
        inc_count = await data_repo.upsert_incidents(incidents_json)

        # Calculate and store metrics
        data = DataFetchResult(
            deployments=all_deployments,
            pull_requests=all_prs,
            incidents=all_incidents,
        )
        metrics = calculate_dora_metrics(data, period)
        snapshot_id = await metrics_repo.create_snapshot(metrics, period)

        await session.commit()

    result = {
        "period_start": period.start_date.isoformat(),
        "period_end": period.end_date.isoformat(),
        "deployments": dep_count,
        "pull_requests": pr_count,
        "incidents": inc_count,
        "snapshot_id": snapshot_id,
    }
    print(f"[Backfill] Completed: {dep_count} deployments, {pr_count} PRs, {inc_count} incidents")
    return result


async def run_backfill(
    start_date: datetime,
    end_date: datetime,
    period_type: str = "weekly",
    delay_seconds: float = 2.0,
) -> AsyncGenerator[dict, None]:
    """Run backfill for all periods in date range.

    Yields progress updates for each completed period.
    """
    periods = generate_periods(start_date, end_date, period_type)
    total = len(periods)

    print(f"[Backfill] Starting backfill: {total} {period_type} periods")
    print(f"[Backfill] Date range: {start_date.date()} to {end_date.date()}")
    print(f"[Backfill] Rate limit delay: {delay_seconds}s between API calls")

    for i, period in enumerate(periods):
        result = await backfill_period(period, delay_seconds)
        result["progress"] = f"{i + 1}/{total}"
        yield result

        # Delay between periods
        if i < total - 1:
            await asyncio.sleep(delay_seconds)

    print(f"[Backfill] Complete: processed {total} periods")
