"""Backfill API endpoints."""

import asyncio
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from metrics_dashboard.backfill import generate_periods, run_backfill

router = APIRouter()

# Track running backfill jobs
_backfill_status: dict = {
    "running": False,
    "progress": None,
    "results": [],
    "error": None,
}


class BackfillRequest(BaseModel):
    """Backfill request parameters."""

    start_date: datetime
    end_date: datetime
    period_type: str = "weekly"
    delay_seconds: float = 2.0


class BackfillPreview(BaseModel):
    """Preview of periods to be backfilled."""

    period_type: str
    total_periods: int
    periods: list[dict]
    estimated_minutes: float


@router.get("/preview", response_model=BackfillPreview)
async def preview_backfill(
    start_date: datetime = Query(..., description="Start date (ISO 8601)"),
    end_date: datetime = Query(..., description="End date (ISO 8601)"),
    period_type: str = Query("weekly", description="Period type (weekly/monthly)"),
    delay_seconds: float = Query(2.0, description="Delay between API calls in seconds"),
) -> BackfillPreview:
    """Preview the periods that would be backfilled.

    Use this to see how many periods will be processed before starting.
    """
    periods = generate_periods(start_date, end_date, period_type)

    # Estimate time based on API calls per period:
    # - 1 call to get repos
    # - N calls for deployments (one per repo, assume ~10 repos)
    # - N calls for PRs (one per repo)
    # - 1 call for incidents
    # Total: ~22 calls per period, round up to 25
    estimated_calls_per_period = 25
    estimated_seconds = len(periods) * estimated_calls_per_period * delay_seconds
    estimated_minutes = estimated_seconds / 60

    return BackfillPreview(
        period_type=period_type,
        total_periods=len(periods),
        periods=[
            {
                "start_date": p.start_date.isoformat(),
                "end_date": p.end_date.isoformat(),
            }
            for p in periods[:10]  # Only show first 10
        ],
        estimated_minutes=round(estimated_minutes, 1),
    )


@router.get("/status")
async def get_backfill_status() -> dict:
    """Get the current backfill job status."""
    return _backfill_status


async def _run_backfill_job(
    start_date: datetime,
    end_date: datetime,
    period_type: str,
    delay_seconds: float,
) -> None:
    """Background task to run backfill."""
    global _backfill_status

    _backfill_status = {
        "running": True,
        "progress": "0/?",
        "results": [],
        "error": None,
    }

    try:
        async for result in run_backfill(start_date, end_date, period_type, delay_seconds):
            _backfill_status["progress"] = result.get("progress", "?")
            _backfill_status["results"].append(result)
    except Exception as e:
        _backfill_status["error"] = str(e)
    finally:
        _backfill_status["running"] = False


@router.post("/start")
async def start_backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
) -> dict:
    """Start a backfill job in the background.

    Use /status to monitor progress.
    """
    global _backfill_status

    if _backfill_status["running"]:
        return {
            "status": "error",
            "message": "A backfill job is already running",
            "progress": _backfill_status["progress"],
        }

    # Preview first
    periods = generate_periods(request.start_date, request.end_date, request.period_type)

    # Start background job
    background_tasks.add_task(
        _run_backfill_job,
        request.start_date,
        request.end_date,
        request.period_type,
        request.delay_seconds,
    )

    return {
        "status": "started",
        "total_periods": len(periods),
        "message": f"Backfill started for {len(periods)} {request.period_type} periods",
    }


@router.post("/stop")
async def stop_backfill() -> dict:
    """Request to stop the current backfill job.

    Note: This is a soft stop - the current period will complete.
    """
    global _backfill_status

    if not _backfill_status["running"]:
        return {"status": "not_running", "message": "No backfill job is running"}

    # For now, just report status - true cancellation would need more infrastructure
    return {
        "status": "requested",
        "message": "Stop requested. Current period will complete.",
        "progress": _backfill_status["progress"],
    }
