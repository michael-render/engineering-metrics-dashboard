"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from metrics_dashboard.api.routers import backfill, metrics, raw_data


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Engineering Metrics API",
        description="DORA metrics and engineering data API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])
    app.include_router(raw_data.router, prefix="/api/v1/raw", tags=["raw-data"])
    app.include_router(backfill.router, prefix="/api/v1/backfill", tags=["backfill"])

    # Health check endpoint
    @app.get("/health", tags=["health"])
    async def health_check() -> dict:
        """Health check endpoint."""
        return {"status": "healthy"}

    # Mount static files for dashboard (if directory exists)
    try:
        app.mount("/", StaticFiles(directory="static", html=True), name="static")
    except RuntimeError:
        # Static directory doesn't exist, skip mounting
        pass

    return app


# Create app instance for uvicorn
app = create_app()
