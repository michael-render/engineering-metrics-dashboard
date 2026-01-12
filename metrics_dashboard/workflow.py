"""Render Workflows implementation for metrics collection.

This module uses the Render Workflows SDK to define tasks that run
in parallel for fetching data from multiple sources.
"""

import asyncio
import os
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from render_sdk.workflows import task, start

from metrics_dashboard.clients import (
    create_github_client,
    create_linear_client,
    create_slab_client,
)
from metrics_dashboard.dora import calculate_dora_metrics
from metrics_dashboard.models import (
    DataFetchResult,
    GitHubDeployment,
    GitHubPullRequest,
    LinearIssue,
    MetricsPeriod,
    SlabPostmortem,
)
from metrics_dashboard.reports import (
    format_report_markdown,
    generate_report,
    send_slack_notification,
)


def get_period(period_type: str) -> MetricsPeriod:
    """Get the metrics period based on type."""
    now = datetime.now(timezone.utc)

    if period_type == "weekly":
        # Last week: Monday to Sunday
        days_since_monday = now.weekday()
        last_monday = now - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)
        return MetricsPeriod(
            type="weekly",
            start_date=last_monday.replace(hour=0, minute=0, second=0, microsecond=0),
            end_date=last_sunday.replace(hour=23, minute=59, second=59, microsecond=0),
        )
    else:
        # Last month
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_of_prev_month = first_of_this_month - timedelta(days=1)
        first_of_prev_month = last_of_prev_month.replace(day=1)
        return MetricsPeriod(
            type="monthly",
            start_date=first_of_prev_month,
            end_date=last_of_prev_month.replace(hour=23, minute=59, second=59),
        )


# =============================================================================
# Render Workflow Tasks - Each runs in its own compute instance
# =============================================================================


@task
async def fetch_github_deployments(period_dict: dict) -> list[dict]:
    """Fetch deployments from GitHub.

    This task runs in its own compute instance and fetches deployment
    data from all repositories in the organization.
    """
    period = MetricsPeriod(**period_dict)
    client = create_github_client()

    print(f"Fetching GitHub deployments for {period.start_date} to {period.end_date}")

    repos = await client.get_repos()
    all_deployments: list[GitHubDeployment] = []

    # Fetch deployments from all repos concurrently
    async def fetch_repo_deployments(repo: str) -> list[GitHubDeployment]:
        try:
            return await client.get_deployments(repo, period)
        except Exception as e:
            print(f"Warning: Failed to fetch deployments for {repo}: {e}")
            return []

    results = await asyncio.gather(*[fetch_repo_deployments(repo) for repo in repos])
    for deployments in results:
        all_deployments.extend(deployments)

    print(f"Found {len(all_deployments)} deployments")
    return [d.model_dump(mode="json") for d in all_deployments]


@task
async def fetch_github_prs(period_dict: dict) -> list[dict]:
    """Fetch merged pull requests from GitHub.

    This task runs in its own compute instance and fetches PR data
    from all repositories in the organization.
    """
    period = MetricsPeriod(**period_dict)
    client = create_github_client()

    print(f"Fetching GitHub PRs for {period.start_date} to {period.end_date}")

    repos = await client.get_repos()
    all_prs: list[GitHubPullRequest] = []

    async def fetch_repo_prs(repo: str) -> list[GitHubPullRequest]:
        try:
            return await client.get_pull_requests(repo, period)
        except Exception as e:
            print(f"Warning: Failed to fetch PRs for {repo}: {e}")
            return []

    results = await asyncio.gather(*[fetch_repo_prs(repo) for repo in repos])
    for prs in results:
        all_prs.extend(prs)

    print(f"Found {len(all_prs)} merged PRs")
    return [pr.model_dump(mode="json") for pr in all_prs]


@task
async def fetch_linear_incidents(period_dict: dict) -> list[dict]:
    """Fetch incident issues from Linear.

    This task runs in its own compute instance and fetches issues
    tagged as incidents from Linear.
    """
    period = MetricsPeriod(**period_dict)
    client = create_linear_client()

    print(f"Fetching Linear incidents for {period.start_date} to {period.end_date}")

    incidents = await client.get_incident_issues(period)

    print(f"Found {len(incidents)} incidents")
    return [i.model_dump(mode="json") for i in incidents]


@task
async def fetch_slab_postmortems(period_dict: dict) -> list[dict]:
    """Fetch postmortem documents from Slab.

    This task runs in its own compute instance and fetches postmortem
    documents from Slab.
    """
    period = MetricsPeriod(**period_dict)
    client = create_slab_client()

    if not client:
        print("Slab client not configured, skipping")
        return []

    print(f"Fetching Slab postmortems for {period.start_date} to {period.end_date}")

    postmortems = await client.get_postmortems(period)

    print(f"Found {len(postmortems)} postmortems")
    return [pm.model_dump(mode="json") for pm in postmortems]


@task
async def aggregate_and_calculate(
    deployments_data: list[dict],
    prs_data: list[dict],
    incidents_data: list[dict],
    postmortems_data: list[dict],
    period_dict: dict,
) -> dict:
    """Aggregate data and calculate DORA metrics.

    This task receives the results from all fetch tasks and calculates
    the final DORA metrics.
    """
    period = MetricsPeriod(**period_dict)

    # Reconstruct models from serialized data
    data = DataFetchResult(
        deployments=[GitHubDeployment(**d) for d in deployments_data],
        pull_requests=[GitHubPullRequest(**pr) for pr in prs_data],
        incidents=[LinearIssue(**i) for i in incidents_data],
        postmortems=[SlabPostmortem(**pm) for pm in postmortems_data],
    )

    print("Calculating DORA metrics...")
    metrics = calculate_dora_metrics(data, period)

    return metrics.model_dump(mode="json")


@task
async def generate_and_send_report(metrics_data: dict) -> str:
    """Generate report and send notifications.

    This task generates the final report and sends it to configured
    notification channels.
    """
    from metrics_dashboard.models import DoraMetrics

    metrics = DoraMetrics(**metrics_data)

    print("Generating report...")
    report = generate_report(metrics)

    # Generate markdown report
    markdown = format_report_markdown(report)
    print("\n" + markdown)

    # Send Slack notification if configured
    slack_webhook = os.environ.get("SLACK_WEBHOOK_URL")
    if slack_webhook:
        await send_slack_notification(report, slack_webhook)

    return markdown


@task
async def run_metrics_workflow(period_type: str = "weekly") -> str:
    """Main workflow orchestrator.

    This is the entry point task that coordinates all other tasks.
    It uses asyncio.gather to run fetch tasks in parallel, leveraging
    Render Workflows' parallel processing capabilities.
    """
    print("=" * 60)
    print("Engineering Metrics Workflow")
    print("=" * 60)

    period = get_period(period_type)
    period_dict = period.model_dump(mode="json")

    print(f"\nReport type: {period_type}")
    print(f"Period: {period.start_date} to {period.end_date}")
    print()

    # Fetch data from all sources in parallel using .map() pattern
    # Each fetch task runs in its own compute instance
    print("--- Fetching data from all sources in parallel ---")

    # Use asyncio.gather for parallel execution across Render Workflow tasks
    deployments_data, prs_data, incidents_data, postmortems_data = await asyncio.gather(
        fetch_github_deployments(period_dict),
        fetch_github_prs(period_dict),
        fetch_linear_incidents(period_dict),
        fetch_slab_postmortems(period_dict),
    )

    print("\n--- Calculating metrics ---")

    # Aggregate and calculate
    metrics_data = await aggregate_and_calculate(
        deployments_data,
        prs_data,
        incidents_data,
        postmortems_data,
        period_dict,
    )

    print("\n--- Generating report ---")

    # Generate and send report
    report = await generate_and_send_report(metrics_data)

    print("\n" + "=" * 60)
    print("Workflow Complete")
    print("=" * 60)

    return report


def main():
    """Entry point for the workflow."""
    load_dotenv()

    period_type = os.environ.get("REPORT_TYPE", "weekly")

    # Start the Render Workflow
    start(run_metrics_workflow, period_type)


if __name__ == "__main__":
    main()
