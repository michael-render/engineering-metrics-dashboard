"""FastAPI entry point for the engineering metrics API.

Run with: uvicorn api_main:app --reload
"""

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from metrics_dashboard.api.app import app  # noqa: E402

__all__ = ["app"]
