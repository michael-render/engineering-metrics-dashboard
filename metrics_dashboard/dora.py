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
    LeadTime,
    LinearIssue,
    MetricsPeriod,
    MTTR,
    SlabPostmortem,
)


def calculate_dora_metrics(data: DataFetchResult, period: MetricsPeriod) -> DoraMetrics:
    """Calculate all DORA metrics from fetched data."""
    return DoraMetrics(
        deployment_frequency=calculate_deployment_frequency(data.deployments, period),
        lead_time=calculate_lead_time(data.pull_requests),
        change_failure_rate=calculate_change_failure_rate(data.deployments, data.incidents),
        mttr=calculate_mttr(data.incidents, data.postmortems),
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
    deployments: list[GitHubDeployment], incidents: list[LinearIssue]
) -> ChangeFailureRate:
    """Calculate change failure rate metric."""
    successful = len([d for d in deployments if d.status == "success"])
    failed = len([d for d in deployments if d.status == "failure"])
    total = successful + failed

    # Count incidents as additional failures
    failures = failed + len(incidents)
    percentage = (failures / total * 100) if total > 0 else 0

    rating = _get_change_failure_rate_rating(percentage)

    return ChangeFailureRate(
        percentage=percentage,
        failed_deployments=failures,
        total_deployments=total,
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


def calculate_mttr(
    incidents: list[LinearIssue], postmortems: list[SlabPostmortem]
) -> MTTR:
    """Calculate mean time to recovery metric."""
    resolution_times: list[float] = []

    for incident in incidents:
        if incident.cycle_time_hours is not None:
            resolution_times.append(incident.cycle_time_hours)

    for pm in postmortems:
        resolution_times.append(pm.time_to_resolve_hours)

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
        incidents=len(incidents) + len(postmortems),
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
