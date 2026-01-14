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
    2. Calculates DORA metrics
    3. Generates and sends the report

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
    # Stage 2: TRANSFORM - Calculate DORA metrics
    # -------------------------------------------------------------------------
    print("--- Stage 2: Calculating DORA metrics ---")

    metrics_json = await calculate_metrics(
        deployments_json,
        prs_json,
        incidents_json,
        period_dict,
    )

    print()

    # -------------------------------------------------------------------------
    # Stage 3: LOAD - Generate report and notify
    # -------------------------------------------------------------------------
    print("--- Stage 3: Generating report and sending notifications ---")

    report_markdown = await generate_and_notify(metrics_json)

    print()
    print("=" * 60)
    print("Pipeline Complete")
    print("=" * 60)

    return report_markdown
