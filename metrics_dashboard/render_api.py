"""Render API client for triggering workflows.

Uses the Render SDK to trigger workflow tasks.
"""

import os
from typing import Any


class RenderAPIError(Exception):
    """Error from Render API."""

    pass


class RenderWorkflowClient:
    """Client for triggering Render Workflow tasks."""

    def __init__(
        self,
        api_key: str | None = None,
        workflow_slug: str | None = None,
    ):
        """Initialize the client.

        Args:
            api_key: Render API key. Falls back to RENDER_API_KEY env var.
            workflow_slug: Workflow slug (e.g., "my-workflow"). Falls back to RENDER_WORKFLOW_SLUG env var.
        """
        self.api_key = api_key or os.environ.get("RENDER_API_KEY")
        self.workflow_slug = workflow_slug or os.environ.get("RENDER_WORKFLOW_SLUG")

        if not self.api_key:
            raise RenderAPIError("RENDER_API_KEY not configured")
        if not self.workflow_slug:
            raise RenderAPIError("RENDER_WORKFLOW_SLUG not configured")

    async def run_task(
        self,
        task_name: str,
        arguments: list[Any] | None = None,
    ) -> dict:
        """Run a workflow task.

        Args:
            task_name: Name of the task to run (e.g., "run_backfill_pipeline")
            arguments: List of arguments to pass to the task

        Returns:
            Task run info including run_id
        """
        try:
            from render_sdk.client import Client
        except ImportError:
            raise RenderAPIError(
                "render_sdk not installed. Add 'render_sdk' to requirements.txt"
            )

        # Task identifier is {workflow-slug}/{task-name}
        task_identifier = f"{self.workflow_slug}/{task_name}"

        try:
            client = Client()
            task_run = await client.workflows.run_task(
                task_identifier,
                arguments or [],
            )

            return {
                "run_id": task_run.id,
                "status": task_run.status,
                "task_identifier": task_identifier,
            }

        except Exception as e:
            raise RenderAPIError(f"Failed to run task: {e}")

    async def get_task_run(self, run_id: str) -> dict:
        """Get status of a task run.

        Args:
            run_id: The task run ID (e.g., "trn-abc123...")

        Returns:
            Task run status info
        """
        try:
            from render_sdk.client import Client
        except ImportError:
            raise RenderAPIError(
                "render_sdk not installed. Add 'render_sdk' to requirements.txt"
            )

        try:
            client = Client()
            task_run = await client.workflows.get_task_run(run_id)

            return {
                "run_id": task_run.id,
                "status": task_run.status,
                "created_at": task_run.created_at.isoformat() if task_run.created_at else None,
                "started_at": task_run.started_at.isoformat() if task_run.started_at else None,
                "finished_at": task_run.finished_at.isoformat() if task_run.finished_at else None,
            }

        except Exception as e:
            raise RenderAPIError(f"Failed to get task run: {e}")


def create_render_client() -> RenderWorkflowClient | None:
    """Create a Render workflow client if configured.

    Returns:
        RenderWorkflowClient if configured, None otherwise
    """
    try:
        return RenderWorkflowClient()
    except RenderAPIError:
        return None
