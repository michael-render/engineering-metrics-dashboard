#!/usr/bin/env python3
"""Trigger the metrics workflow via Render API.

This script is called by cron jobs to run the workflow on a schedule.
It uses the Render Workflows SDK client to trigger the run_metrics_pipeline task.

Usage:
    python scripts/trigger_workflow.py weekly
    python scripts/trigger_workflow.py monthly

Environment variables required:
    RENDER_API_KEY: Your Render API key
    WORKFLOW_SERVICE_ID: The service ID of your workflow (optional, uses slug if not set)
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

load_dotenv()


async def trigger_workflow(period_type: str) -> None:
    """Trigger the metrics workflow via Render SDK."""
    from render_sdk.client import Client

    api_key = os.environ.get("RENDER_API_KEY")
    if not api_key:
        print("Error: RENDER_API_KEY environment variable is required")
        sys.exit(1)

    # The task identifier format is: {workflow-slug}/{task-name}
    # or just {task-name} if running from within the same workflow
    workflow_id = os.environ.get("WORKFLOW_SERVICE_ID", "engineering-metrics-dashboard")
    task_identifier = f"{workflow_id}/run_metrics_pipeline"

    print(f"Triggering workflow task: {task_identifier}")
    print(f"Period type: {period_type}")

    async with Client() as client:
        # Run the task with the period type as argument
        task_run = await client.workflows.run_task(
            task_identifier,
            [period_type],  # Arguments as JSON array
        )

        print(f"Task run started: {task_run.id}")
        print(f"Status: {task_run.status}")

        # Wait for completion
        result = await task_run
        print(f"Task completed with status: {result.status}")

        if result.status == "succeeded":
            print("Workflow completed successfully!")
        else:
            print(f"Workflow failed: {result.error}")
            sys.exit(1)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/trigger_workflow.py <weekly|monthly>")
        sys.exit(1)

    period_type = sys.argv[1]
    if period_type not in ("weekly", "monthly"):
        print(f"Invalid period type: {period_type}. Must be 'weekly' or 'monthly'.")
        sys.exit(1)

    asyncio.run(trigger_workflow(period_type))


if __name__ == "__main__":
    main()
