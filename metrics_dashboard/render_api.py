"""Render API client for triggering workflows.

Uses the Render REST API directly via httpx.
"""

import os
from typing import Any

import httpx


RENDER_API_BASE = "https://api.render.com/v1"


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

    def _headers(self) -> dict:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
        # Task identifier is {workflow-slug}/{task-name}
        task_identifier = f"{self.workflow_slug}/{task_name}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{RENDER_API_BASE}/tasks",
                    headers=self._headers(),
                    json={
                        "task": task_identifier,
                        "input": arguments or [],
                    },
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "run_id": data.get("id"),
                    "status": data.get("status"),
                    "task_identifier": task_identifier,
                }

            except httpx.HTTPStatusError as e:
                raise RenderAPIError(f"API error {e.response.status_code}: {e.response.text}")
            except Exception as e:
                raise RenderAPIError(f"Failed to run task: {e}")

    async def get_task_run(self, run_id: str) -> dict:
        """Get status of a task run.

        Args:
            run_id: The task run ID (e.g., "trn-abc123...")

        Returns:
            Task run status info
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{RENDER_API_BASE}/tasks/{run_id}",
                    headers=self._headers(),
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "run_id": data.get("id"),
                    "status": data.get("status"),
                    "created_at": data.get("createdAt"),
                    "started_at": data.get("startedAt"),
                    "finished_at": data.get("finishedAt"),
                }

            except httpx.HTTPStatusError as e:
                raise RenderAPIError(f"API error {e.response.status_code}: {e.response.text}")
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
