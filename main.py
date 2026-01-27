"""Entry point for Render Workflows.

This file registers all tasks with Render Workflows and starts the task server.
To deploy: Create a Workflow service in the Render Dashboard and point it to this repo.
"""

import logging
import os
import sys

# Configure logging FIRST before any other imports
# This ensures we capture any errors during module imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def validate_environment() -> list[str]:
    """Validate required environment variables and return list of issues."""
    issues = []

    # Required for all workflows
    required_vars = {
        "DATABASE_URL": "PostgreSQL connection (link from metrics-db)",
        "GITHUB_TOKEN": "GitHub personal access token",
        "GITHUB_ORG": "GitHub organization name",
    }

    # Optional but recommended
    optional_vars = {
        "INCIDENT_IO_API_KEY": "incident.io API key (for MTTR metrics)",
        "SLACK_WEBHOOK_URL": "Slack webhook (for notifications)",
    }

    logger.info("Validating environment variables...")

    for var, description in required_vars.items():
        if not os.environ.get(var):
            issues.append(f"  - {var}: {description}")
        else:
            # Mask sensitive values in logs
            value = os.environ[var]
            if "TOKEN" in var or "KEY" in var or "URL" in var:
                masked = value[:8] + "..." if len(value) > 8 else "***"
            else:
                masked = value
            logger.info(f"  ✓ {var}={masked}")

    for var, description in optional_vars.items():
        if not os.environ.get(var):
            logger.info(f"  ○ {var} not set ({description})")
        else:
            logger.info(f"  ✓ {var}=***")

    return issues


def main() -> None:
    """Start the workflow service with proper validation and logging."""
    logger.info("=" * 70)
    logger.info("Engineering Metrics Dashboard - Workflow Service")
    logger.info("=" * 70)

    # Validate environment before importing tasks
    # This catches configuration issues early
    issues = validate_environment()

    if issues:
        logger.warning("")
        logger.warning("Missing required environment variables:")
        for issue in issues:
            logger.warning(issue)
        logger.warning("")
        logger.warning("Configure these in the Render Workflow settings.")
        logger.warning("Tasks may fail if these are not set.")
        logger.warning("")

    # Import tasks module to register @task decorated functions
    logger.info("")
    logger.info("Registering workflow tasks...")

    try:
        from metrics_dashboard import tasks  # noqa: F401

        # List registered tasks for visibility
        registered_tasks = [
            "run_metrics_pipeline",
            "run_backfill_pipeline",
            "fetch_github_deployments",
            "fetch_github_pull_requests",
            "fetch_incidents",
            "calculate_metrics",
            "store_raw_data",
            "store_metrics_snapshot",
            "generate_and_notify",
        ]
        logger.info("")
        logger.info("Registered tasks:")
        for task_name in registered_tasks:
            logger.info(f"  - {task_name}")

    except Exception as e:
        logger.error(f"Failed to import tasks module: {e}", exc_info=True)
        sys.exit(1)

    logger.info("")
    logger.info("=" * 70)
    logger.info("Starting workflow service...")
    logger.info("Ready to accept task executions!")
    logger.info("=" * 70)

    # Start the workflow service
    from render_sdk.workflows import start

    start()


if __name__ == "__main__":
    main()
