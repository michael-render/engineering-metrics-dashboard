"""Entry point for Render Workflows.

This file registers all tasks with Render Workflows and starts the task server.
To deploy: Create a Workflow service in the Render Dashboard and point it to this repo.
"""

from render_sdk.workflows import start

# Import all task modules to register them
from metrics_dashboard import tasks  # noqa: F401

if __name__ == "__main__":
    start()
