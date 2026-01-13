"""DORA metrics calculation."""

from datetime import datetime
from statistics import median

from metrics_dashboard.models import (
    ChangeFailureRate,
    DataFetchResult,
    DeploymentFrequency,
    DoraMetrics,
    DoraRating,
    GitHubDeployment,
    GitHubPullRequest,
    Incident,
    LeadTime,
    MetricsPeriod,
    MTTR,
)


def calculate_dora_metrics(data: DataFetchResult, period: MetricsPeriod) -> DoraMetrics:
    """Calculate all DORA metrics from fetched data."""
    # Filter to only change-related incidents for DORA metrics
    change_incidents = [inc for inc in data.incidents if inc.is_change_related]

    return DoraMetrics(
        deployment_frequency=calculate_deployment_frequency(data.deployments, period),
        lead_time=calculate_lead_time(data.pull_requests),
        change_failure_rate=calculate_change_failure_rate(data.deployments, change_incidents),
        mttr=calculate_mttr(change_incidents),
        period=period,
        generated_at=datetime.now(),
    )


def calculate_deployment_frequency(
    deployments: list[GitHubDeployment], period: MetricsPeriod
) -> DeploymentFrequency:
    """Calculate deployment frequency metric."""
    successful = [d for d in deployments if d.status == "success"]
    total = len(successful)

    days = max((period.end_date - period.start_date).days, 1)
    per_day = total / days
    per_week = per_day * 7

    rating = _get_deployment_frequency_rating(per_day)

    return DeploymentFrequency(
        deployments_per_day=per_day,
        deployments_per_week=per_week,
        total_deployments=total,
        rating=rating,
    )


def _get_deployment_frequency_rating(per_day: float) -> DoraRating:
    """Get rating for deployment frequency."""
    if per_day >= 1:
        return DoraRating.ELITE
    elif per_day >= 1 / 7:
        return DoraRating.HIGH
    elif per_day >= 1 / 30:
        return DoraRating.MEDIUM
    return DoraRating.LOW


def calculate_lead_time(pull_requests: list[GitHubPullRequest]) -> LeadTime:
    """Calculate lead time for changes metric."""
    lead_times: list[float] = []

    for pr in pull_requests:
        if not pr.merged_at:
            continue

        start_time = pr.first_commit_at or pr.created_at
        hours = (pr.merged_at - start_time).total_seconds() / 3600
        lead_times.append(hours)

    if not lead_times:
        return LeadTime(
            average_hours=0,
            median_hours=0,
            p90_hours=0,
            rating=DoraRating.LOW,
        )

    sorted_times = sorted(lead_times)
    avg = sum(lead_times) / len(lead_times)
    med = median(lead_times)
    p90_idx = int(len(sorted_times) * 0.9)
    p90 = sorted_times[p90_idx] if p90_idx < len(sorted_times) else med

    rating = _get_lead_time_rating(med)

    return LeadTime(
        average_hours=avg,
        median_hours=med,
        p90_hours=p90,
        rating=rating,
    )


def _get_lead_time_rating(median_hours: float) -> DoraRating:
    """Get rating for lead time."""
    if median_hours < 1:
        return DoraRating.ELITE
    elif median_hours < 24:
        return DoraRating.HIGH
    elif median_hours < 168:  # 1 week
        return DoraRating.MEDIUM
    return DoraRating.LOW


def calculate_change_failure_rate(
    deployments: list[GitHubDeployment], incidents: list[Incident]
) -> ChangeFailureRate:
    """Calculate change failure rate metric.

    Per DORA definition: The percentage of deployments causing a failure
    in production that requires remediation (rollback, hotfix, patch).

    We count incidents from incident.io that are marked as change-related.
    """
    successful_deployments = len([d for d in deployments if d.status == "success"])
    total_deployments = successful_deployments

    if total_deployments == 0:
        return ChangeFailureRate(
            percentage=0,
            failed_changes=0,
            total_deployments=0,
            rating=DoraRating.ELITE,
        )

    # Count change-related incidents as failed changes
    failed_changes = len(incidents)

    percentage = (failed_changes / total_deployments * 100) if total_deployments > 0 else 0

    rating = _get_change_failure_rate_rating(percentage)

    return ChangeFailureRate(
        percentage=percentage,
        failed_changes=failed_changes,
        total_deployments=total_deployments,
        rating=rating,
    )


def _get_change_failure_rate_rating(percentage: float) -> DoraRating:
    """Get rating for change failure rate."""
    if percentage <= 5:
        return DoraRating.ELITE
    elif percentage <= 10:
        return DoraRating.HIGH
    elif percentage <= 15:
        return DoraRating.MEDIUM
    return DoraRating.LOW


def calculate_mttr(incidents: list[Incident]) -> MTTR:
    """Calculate mean time to recovery metric.

    Per DORA definition: How long it takes to restore service when a
    service incident or defect that impacts users occurs.
    """
    resolution_times: list[float] = []

    for incident in incidents:
        if incident.time_to_resolve_hours is not None:
            resolution_times.append(incident.time_to_resolve_hours)

    if not resolution_times:
        return MTTR(
            average_hours=0,
            median_hours=0,
            incidents=0,
            rating=DoraRating.ELITE,  # No incidents is elite
        )

    avg = sum(resolution_times) / len(resolution_times)
    med = median(resolution_times)
    rating = _get_mttr_rating(med)

    return MTTR(
        average_hours=avg,
        median_hours=med,
        incidents=len(incidents),
        rating=rating,
    )


def _get_mttr_rating(median_hours: float) -> DoraRating:
    """Get rating for MTTR."""
    if median_hours < 1:
        return DoraRating.ELITE
    elif median_hours < 24:
        return DoraRating.HIGH
    elif median_hours < 168:  # 1 week
        return DoraRating.MEDIUM
    return DoraRating.LOW


def get_overall_rating(metrics: DoraMetrics) -> DoraRating:
    """Calculate overall DORA rating."""
    ratings = [
        metrics.deployment_frequency.rating,
        metrics.lead_time.rating,
        metrics.change_failure_rate.rating,
        metrics.mttr.rating,
    ]

    values = {
        DoraRating.ELITE: 4,
        DoraRating.HIGH: 3,
        DoraRating.MEDIUM: 2,
        DoraRating.LOW: 1,
    }

    avg = sum(values[r] for r in ratings) / len(ratings)

    if avg >= 3.5:
        return DoraRating.ELITE
    elif avg >= 2.5:
        return DoraRating.HIGH
    elif avg >= 1.5:
        return DoraRating.MEDIUM
    return DoraRating.LOW


def format_rating(rating: DoraRating) -> str:
    """Format rating for display."""
    labels = {
        DoraRating.ELITE: "Elite Performer",
        DoraRating.HIGH: "High Performer",
        DoraRating.MEDIUM: "Medium Performer",
        DoraRating.LOW: "Low Performer",
    }
    return labels[rating]
