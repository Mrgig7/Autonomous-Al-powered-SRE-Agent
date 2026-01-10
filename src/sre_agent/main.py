"""FastAPI application entry point.

This is the main application module that configures and starts
the SRE Agent API server.
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sre_agent import __version__
from sre_agent.api.health import router as health_router
from sre_agent.api.webhooks.github import router as github_router
from sre_agent.config import get_settings
from sre_agent.core.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    setup_logging()
    settings = get_settings()
    logger.info(
        "SRE Agent starting",
        extra={
            "version": __version__,
            "environment": settings.environment,
        },
    )

    yield

    # Shutdown
    logger.info("SRE Agent shutting down")


def create_app() -> FastAPI:
    """
    Application factory for creating the FastAPI app.

    Returns:
        Configured FastAPI application
    """
    settings = get_settings()

    app = FastAPI(
        title="SRE Agent",
        description="Self-Healing CI/CD Platform - Autonomous AI-powered SRE Agent",
        version=__version__,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        logger.warning(
            "Request validation failed",
            extra={"errors": exc.errors(), "path": request.url.path},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )

    # Include routers
    app.include_router(health_router)
    app.include_router(github_router)

    # Root endpoint
    @app.get("/")
    async def root() -> dict:
        """Root endpoint with API info."""
        return {
            "name": "SRE Agent",
            "version": __version__,
            "docs": "/docs" if not settings.is_production else None,
        }

    return app


# Create the application instance
app = create_app()
