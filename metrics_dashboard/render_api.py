"""Render API client for triggering workflows."""

import os
from typing import Any

import httpx


class RenderAPIError(Exception):
    """Error from Render API."""

    pass


class RenderAPIClient:
    """Client for interacting with the Render API."""

    BASE_URL = "https://api.render.com/v1"

    def __init__(self, api_key: str | None = None, workflow_id: str | None = None):
        self.api_key = api_key or os.environ.get("RENDER_API_KEY")
        self.workflow_id = workflow_id or os.environ.get("RENDER_WORKFLOW_ID")

        if not self.api_key:
            raise RenderAPIError("RENDER_API_KEY not configured")
        if not self.workflow_id:
            raise RenderAPIError("RENDER_WORKFLOW_ID not configured")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def trigger_workflow(
        self,
        task_name: str,
        parameters: dict[str, Any] | None = None,
    ) -> dict:
        """Trigger a workflow task.

        Args:
            task_name: Name of the task to run (e.g., "run_backfill_pipeline")
            parameters: Parameters to pass to the task

        Returns:
            Job info from Render API
        """
        url = f"{self.BASE_URL}/workflows/{self.workflow_id}/runs"

        payload = {
            "taskName": task_name,
        }
        if parameters:
            payload["parameters"] = parameters

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=30.0,
            )

            if response.status_code == 401:
                raise RenderAPIError("Invalid RENDER_API_KEY")
            if response.status_code == 404:
                raise RenderAPIError(f"Workflow {self.workflow_id} not found")
            if response.status_code >= 400:
                raise RenderAPIError(f"Render API error: {response.status_code} - {response.text}")

            return response.json()

    async def get_workflow_run(self, run_id: str) -> dict:
        """Get status of a workflow run.

        Args:
            run_id: The workflow run ID

        Returns:
            Run status from Render API
        """
        url = f"{self.BASE_URL}/workflows/{self.workflow_id}/runs/{run_id}"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self.headers,
                timeout=30.0,
            )

            if response.status_code >= 400:
                raise RenderAPIError(f"Render API error: {response.status_code} - {response.text}")

            return response.json()


def create_render_client() -> RenderAPIClient | None:
    """Create a Render API client if configured.

    Returns:
        RenderAPIClient if configured, None otherwise
    """
    try:
        return RenderAPIClient()
    except RenderAPIError:
        return None
