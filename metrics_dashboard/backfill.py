"""Backfill utilities for historical metrics data."""

from datetime import datetime, timedelta, timezone

from metrics_dashboard.models import MetricsPeriod


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
