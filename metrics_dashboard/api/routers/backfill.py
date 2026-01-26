"""Backfill API endpoints.

Triggers Render Workflows for backfilling historical data.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from metrics_dashboard.backfill import generate_periods
from metrics_dashboard.logging_config import get_logger
from metrics_dashboard.render_api import RenderAPIError, create_render_client

router = APIRouter()
logger = get_logger("api.backfill")

# Track the current backfill run
_current_run: dict | None = None


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
    """Get the current backfill job status.

    Checks status with Render API if a run is in progress.
    """
    global _current_run

    if not _current_run:
        return {
            "running": False,
            "progress": None,
            "results": [],
            "error": None,
        }

    # Check with Render API for current status
    client = create_render_client()
    if not client:
        return {
            "running": False,
            "progress": None,
            "results": [],
            "error": "Render API not configured",
        }

    try:
        run_status = await client.get_task_run(_current_run["run_id"])
        status = run_status.get("status", "unknown")

        if status in ("pending", "running"):
            return {
                "running": True,
                "progress": _current_run.get("progress", "Running..."),
                "results": [],
                "error": None,
                "run_id": _current_run["run_id"],
                "render_status": status,
            }
        elif status == "succeeded":
            # Clear the run since it's complete
            run_info = _current_run
            _current_run = None
            return {
                "running": False,
                "progress": "Complete",
                "results": [],
                "error": None,
                "run_id": run_info["run_id"],
                "render_status": status,
            }
        else:
            # Failed or cancelled
            error_msg = f"Workflow {status}"
            run_info = _current_run
            _current_run = None
            return {
                "running": False,
                "progress": None,
                "results": [],
                "error": error_msg,
                "run_id": run_info["run_id"],
                "render_status": status,
            }
    except RenderAPIError as e:
        return {
            "running": _current_run is not None,
            "progress": _current_run.get("progress") if _current_run else None,
            "results": [],
            "error": str(e),
        }


@router.post("/start")
async def start_backfill(request: BackfillRequest) -> dict:
    """Start a backfill job by triggering a Render Workflow.

    The workflow runs asynchronously. Use /status to monitor progress.
    """
    global _current_run

    # Check if already running
    if _current_run:
        return {
            "status": "error",
            "message": "A backfill job is already running",
            "run_id": _current_run.get("run_id"),
        }

    # Get Render API client
    client = create_render_client()
    if not client:
        logger.warning(
            "Backfill unavailable: Render API not configured",
            extra={
                "extra": {
                    "endpoint": "/api/v1/backfill/start",
                    "error_type": "configuration_error",
                    "missing_config": ["RENDER_API_KEY", "RENDER_WORKFLOW_SLUG"],
                }
            },
        )
        raise HTTPException(
            status_code=503,
            detail="Backfill not available: RENDER_API_KEY or RENDER_WORKFLOW_SLUG not configured. "
            "Add these environment variables to the web service.",
        )

    # Preview to get period count
    periods = generate_periods(request.start_date, request.end_date, request.period_type)

    try:
        # Trigger the workflow task
        # Arguments are passed as a list in the same order as the task function signature
        result = await client.run_task(
            task_name="run_backfill_pipeline",
            arguments=[
                request.start_date.isoformat(),  # start_date_iso
                request.end_date.isoformat(),    # end_date_iso
                request.period_type,              # period_type
                request.delay_seconds,            # delay_seconds
            ],
        )

        run_id = result.get("run_id")
        _current_run = {
            "run_id": run_id,
            "started_at": datetime.utcnow().isoformat(),
            "total_periods": len(periods),
            "progress": f"0/{len(periods)}",
        }

        logger.info(
            f"Backfill workflow started: {run_id}",
            extra={
                "extra": {
                    "endpoint": "/api/v1/backfill/start",
                    "run_id": run_id,
                    "total_periods": len(periods),
                    "period_type": request.period_type,
                    "start_date": request.start_date.isoformat(),
                    "end_date": request.end_date.isoformat(),
                }
            },
        )

        return {
            "status": "started",
            "run_id": run_id,
            "total_periods": len(periods),
            "message": f"Backfill workflow started for {len(periods)} {request.period_type} periods",
        }

    except RenderAPIError as e:
        logger.error(
            f"Failed to trigger backfill workflow: {e}",
            exc_info=True,
            extra={
                "extra": {
                    "endpoint": "/api/v1/backfill/start",
                    "error_type": "render_api_error",
                    "error_message": str(e),
                    "request_params": {
                        "start_date": request.start_date.isoformat(),
                        "end_date": request.end_date.isoformat(),
                        "period_type": request.period_type,
                        "delay_seconds": request.delay_seconds,
                    },
                    "total_periods": len(periods),
                }
            },
        )
        raise HTTPException(status_code=502, detail=f"Failed to trigger workflow: {e}")


@router.post("/stop")
async def stop_backfill() -> dict:
    """Request to stop the current backfill job.

    Note: Render Workflows cannot be stopped mid-run. This just clears our tracking.
    """
    global _current_run

    if not _current_run:
        return {"status": "not_running", "message": "No backfill job is running"}

    run_id = _current_run.get("run_id")
    _current_run = None

    return {
        "status": "cleared",
        "message": "Backfill tracking cleared. Note: The workflow may still be running on Render.",
        "run_id": run_id,
    }
