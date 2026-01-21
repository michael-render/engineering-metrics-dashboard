"""Render Workflow tasks for engineering metrics collection.

Each @task decorated function runs in its own compute instance.
Subtasks called with asyncio.gather() execute in parallel.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

from render_sdk.workflows import task

from metrics_dashboard.clients import (
    create_github_client,
    create_incident_io_client,
)
from metrics_dashboard.dora import calculate_dora_metrics
from metrics_dashboard.models import (
    DataFetchResult,
    GitHubDeployment,
    GitHubPullRequest,
    Incident,
    MetricsPeriod,
)
from metrics_dashboard.reports import (
    format_report_markdown,
    generate_report,
    send_slack_notification,
)


def _get_period(period_type: str) -> MetricsPeriod:
    """Get the metrics period based on type."""
    now = datetime.now(timezone.utc)

    if period_type == "weekly":
        days_since_monday = now.weekday()
        last_monday = now - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)
        return MetricsPeriod(
            type="weekly",
            start_date=last_monday.replace(hour=0, minute=0, second=0, microsecond=0),
            end_date=last_sunday.replace(hour=23, minute=59, second=59, microsecond=0),
        )
    else:
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)
        return MetricsPeriod(
            type="monthly",
            start_date=first_of_prev_month,
            end_date=last_of_prev_month.replace(hour=23, minute=59, second=59),
        )


# =============================================================================
# Data Fetching Tasks - These run in parallel via asyncio.gather()
# =============================================================================


@task
async def fetch_github_deployments(period_dict: dict) -> list[dict]:
    """Fetch deployments from all GitHub repos.

    Runs in its own compute instance. Called as a subtask from the orchestrator.
    """
    period = MetricsPeriod(**period_dict)
    client = create_github_client()

    print(f"[GitHub Deployments] Fetching for {period.start_date.date()} to {period.end_date.date()}")

    repos = await client.get_repos()
    all_deployments: list[GitHubDeployment] = []

    async def fetch_repo(repo: str) -> list[GitHubDeployment]:
        try:
            return await client.get_deployments(repo, period)
        except Exception as e:
            print(f"[GitHub Deployments] Warning: {repo} failed: {e}")
            return []

    results = await asyncio.gather(*[fetch_repo(repo) for repo in repos])
    for deps in results:
        all_deployments.extend(deps)

    print(f"[GitHub Deployments] Found {len(all_deployments)} deployments across {len(repos)} repos")
    return [d.model_dump(mode="json") for d in all_deployments]


@task
async def fetch_github_pull_requests(period_dict: dict) -> list[dict]:
    """Fetch merged PRs from all GitHub repos.

    Runs in its own compute instance. Called as a subtask from the orchestrator.
    """
    period = MetricsPeriod(**period_dict)
    client = create_github_client()

    print(f"[GitHub PRs] Fetching for {period.start_date.date()} to {period.end_date.date()}")

    repos = await client.get_repos()
    all_prs: list[GitHubPullRequest] = []

    async def fetch_repo(repo: str) -> list[GitHubPullRequest]:
        try:
            return await client.get_pull_requests(repo, period)
        except Exception as e:
            print(f"[GitHub PRs] Warning: {repo} failed: {e}")
            return []

    results = await asyncio.gather(*[fetch_repo(repo) for repo in repos])
    for prs in results:
        all_prs.extend(prs)

    print(f"[GitHub PRs] Found {len(all_prs)} merged PRs across {len(repos)} repos")
    return [pr.model_dump(mode="json") for pr in all_prs]


@task
async def fetch_incidents(period_dict: dict) -> list[dict]:
    """Fetch incidents from incident.io.

    Runs in its own compute instance. Called as a subtask from the orchestrator.
    Fetches DORA-relevant incidents (change-related AND user-impacting).

    Per DORA definition, MTTR measures "time to restore service when a
    service incident or defect that impacts users occurs."
    """
    period = MetricsPeriod(**period_dict)
    client = create_incident_io_client()

    if not client:
        print("[incident.io] Client not configured, skipping")
        return []

    print(f"[incident.io] Fetching incidents for {period.start_date.date()} to {period.end_date.date()}")

    incidents = await client.get_dora_incidents(period)

    print(f"[incident.io] Found {len(incidents)} DORA-relevant incidents (change-related + user-impacting)")
    return [inc.model_dump(mode="json") for inc in incidents]


# =============================================================================
# Processing Tasks
# =============================================================================


@task
async def calculate_metrics(
    deployments_json: list[dict],
    prs_json: list[dict],
    incidents_json: list[dict],
    period_dict: dict,
) -> dict:
    """Calculate DORA metrics from fetched data.

    Receives results from all fetch tasks and computes the final metrics.
    """
    print("[Metrics] Calculating DORA metrics...")

    period = MetricsPeriod(**period_dict)

    data = DataFetchResult(
        deployments=[GitHubDeployment(**d) for d in deployments_json],
        pull_requests=[GitHubPullRequest(**pr) for pr in prs_json],
        incidents=[Incident(**inc) for inc in incidents_json],
    )

    metrics = calculate_dora_metrics(data, period)

    print(f"[Metrics] Deployment frequency: {metrics.deployment_frequency.deployments_per_day:.2f}/day")
    print(f"[Metrics] Lead time: {metrics.lead_time.median_hours:.1f} hours")
    print(f"[Metrics] Change failure rate: {metrics.change_failure_rate.percentage:.1f}%")
    print(f"[Metrics] MTTR: {metrics.mttr.median_hours:.1f} hours")

    return metrics.model_dump(mode="json")


# =============================================================================
# Storage Tasks - Store data in PostgreSQL
# =============================================================================


@task
async def store_raw_data(
    deployments_json: list[dict],
    prs_json: list[dict],
    incidents_json: list[dict],
) -> dict:
    """Store fetched data in PostgreSQL.

    Uses upsert (INSERT ... ON CONFLICT UPDATE) to handle re-runs gracefully.
    Returns counts of inserted/updated records.
    """
    from metrics_dashboard.database.repository import DataRepository
    from metrics_dashboard.database.session import get_async_session

    print("[Storage] Storing raw data in database...")

    async with get_async_session() as session:
        repo = DataRepository(session)

        dep_count = await repo.upsert_deployments(deployments_json)
        pr_count = await repo.upsert_pull_requests(prs_json)
        inc_count = await repo.upsert_incidents(incidents_json)

        await session.commit()

    result = {
        "deployments_stored": dep_count,
        "pull_requests_stored": pr_count,
        "incidents_stored": inc_count,
    }

    print(f"[Storage] Stored: {dep_count} deployments, {pr_count} PRs, {inc_count} incidents")
    return result


@task
async def store_metrics_snapshot(metrics_json: dict, period_dict: dict) -> int:
    """Store calculated DORA metrics as a historical snapshot.

    Returns the snapshot ID.
    """
    from metrics_dashboard.database.repository import MetricsRepository
    from metrics_dashboard.database.session import get_async_session
    from metrics_dashboard.models import DoraMetrics

    print("[Storage] Storing metrics snapshot...")

    metrics = DoraMetrics(**metrics_json)
    period = MetricsPeriod(**period_dict)

    async with get_async_session() as session:
        repo = MetricsRepository(session)
        snapshot_id = await repo.create_snapshot(metrics, period)
        await session.commit()

    print(f"[Storage] Created metrics snapshot with ID: {snapshot_id}")
    return snapshot_id


@task
async def generate_and_notify(metrics_json: dict) -> str:
    """Generate report and send notifications.

    Creates the final Markdown report and sends to Slack if configured.
    """
    from metrics_dashboard.models import DoraMetrics

    print("[Report] Generating report...")

    metrics = DoraMetrics(**metrics_json)
    report = generate_report(metrics)
    markdown = format_report_markdown(report)

    print("\n" + "=" * 60)
    print(markdown)
    print("=" * 60 + "\n")

    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if slack_webhook:
        print("[Report] Sending Slack notification...")
        await send_slack_notification(report, slack_webhook)
        print("[Report] Slack notification sent")

    return markdown


# =============================================================================
# Main Orchestrator Task
# =============================================================================


@task
async def run_metrics_pipeline(period_type: str = "weekly") -> str:
    """Main orchestrator for the metrics pipeline.

    This task coordinates all other tasks:
    1. Fetches data from all sources IN PARALLEL using asyncio.gather()
    2. Stores raw data in PostgreSQL
    3. Calculates DORA metrics
    4. Stores metrics snapshot in PostgreSQL
    5. Generates and sends the report

    Args:
        period_type: Either "weekly" or "monthly"

    Returns:
        The generated Markdown report
    """
    print("=" * 60)
    print("Engineering Metrics Pipeline")
    print("=" * 60)

    period = _get_period(period_type)
    period_dict = period.model_dump(mode="json")

    print(f"Report type: {period_type}")
    print(f"Period: {period.start_date.date()} to {period.end_date.date()}")
    print()

    # -------------------------------------------------------------------------
    # Stage 1: EXTRACT - Fetch from all data sources IN PARALLEL
    # Each subtask runs in its own compute instance
    # -------------------------------------------------------------------------
    print("--- Stage 1: Fetching data from all sources in parallel ---")

    deployments_json, prs_json, incidents_json = await asyncio.gather(
        fetch_github_deployments(period_dict),
        fetch_github_pull_requests(period_dict),
        fetch_incidents(period_dict),
    )

    print()
    print(f"Fetched: {len(deployments_json)} deployments, {len(prs_json)} PRs, "
          f"{len(incidents_json)} incidents")
    print()

    # -------------------------------------------------------------------------
    # Stage 2: STORE RAW DATA - Persist to PostgreSQL
    # -------------------------------------------------------------------------
    print("--- Stage 2: Storing raw data in database ---")

    storage_result = await store_raw_data(
        deployments_json,
        prs_json,
        incidents_json,
    )

    print()

    # -------------------------------------------------------------------------
    # Stage 3: TRANSFORM - Calculate DORA metrics
    # -------------------------------------------------------------------------
    print("--- Stage 3: Calculating DORA metrics ---")

    metrics_json = await calculate_metrics(
        deployments_json,
        prs_json,
        incidents_json,
        period_dict,
    )

    print()

    # -------------------------------------------------------------------------
    # Stage 4: STORE SNAPSHOT - Save metrics to PostgreSQL for historical tracking
    # -------------------------------------------------------------------------
    print("--- Stage 4: Storing metrics snapshot ---")

    snapshot_id = await store_metrics_snapshot(metrics_json, period_dict)

    print()

    # -------------------------------------------------------------------------
    # Stage 5: LOAD - Generate report and notify
    # -------------------------------------------------------------------------
    print("--- Stage 5: Generating report and sending notifications ---")

    report_markdown = await generate_and_notify(metrics_json)

    print()
    print("=" * 60)
    print("Pipeline Complete")
    print("=" * 60)

    return report_markdown


# =============================================================================
# Backfill Task - For historical data
# =============================================================================


@task
async def run_backfill_pipeline(
    start_date_iso: str,
    end_date_iso: str,
    period_type: str = "weekly",
    delay_seconds: float = 2.0,
) -> dict:
    """Backfill historical metrics data for a date range.

    This task fetches and stores data for multiple periods, processing them
    sequentially with a delay between API calls to respect rate limits.

    Args:
        start_date_iso: Start date in ISO format (e.g., "2024-01-01T00:00:00Z")
        end_date_iso: End date in ISO format (e.g., "2024-12-31T23:59:59Z")
        period_type: Either "weekly" or "monthly"
        delay_seconds: Delay between API calls for rate limiting

    Returns:
        Summary of backfill results
    """
    from metrics_dashboard.backfill import generate_periods, backfill_period

    start_date = datetime.fromisoformat(start_date_iso.replace("Z", "+00:00"))
    end_date = datetime.fromisoformat(end_date_iso.replace("Z", "+00:00"))

    print("=" * 60)
    print("Backfill Pipeline")
    print("=" * 60)
    print(f"Date range: {start_date.date()} to {end_date.date()}")
    print(f"Period type: {period_type}")
    print(f"Rate limit delay: {delay_seconds}s")
    print()

    periods = generate_periods(start_date, end_date, period_type)
    total = len(periods)
    print(f"Total periods to process: {total}")
    print()

    results = []
    for i, period in enumerate(periods):
        print(f"--- Processing period {i + 1}/{total} ---")
        try:
            result = await backfill_period(period, delay_seconds)
            result["progress"] = f"{i + 1}/{total}"
            results.append(result)
            print(f"Completed: {result['deployments']} deployments, "
                  f"{result['pull_requests']} PRs, {result['incidents']} incidents")
        except Exception as e:
            print(f"Error processing period: {e}")
            results.append({
                "period_start": period.start_date.isoformat(),
                "period_end": period.end_date.isoformat(),
                "error": str(e),
                "progress": f"{i + 1}/{total}",
            })

        # Delay between periods (except for the last one)
        if i < total - 1:
            await asyncio.sleep(delay_seconds)

        print()

    print("=" * 60)
    print("Backfill Complete")
    print("=" * 60)
    print(f"Processed {len(results)} periods")

    successful = len([r for r in results if "error" not in r])
    failed = len([r for r in results if "error" in r])
    print(f"Successful: {successful}, Failed: {failed}")

    return {
        "total_periods": total,
        "successful": successful,
        "failed": failed,
        "results": results,
    }
