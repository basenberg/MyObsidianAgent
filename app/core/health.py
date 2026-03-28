"""Health check endpoints for monitoring application and database status."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.logging import get_logger

logger = get_logger(__name__)

# Health check endpoints are typically at root (no prefix)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint.

    Returns:
        dict: Health status of the API service.

    Example response:
        {"status": "healthy", "service": "api"}
    """
    return {"status": "healthy", "service": "api"}


@router.get("/health/db")
async def database_health_check(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Database connectivity health check.

    Args:
        db: Database session dependency.

    Returns:
        dict: Health status of the database connection.

    Raises:
        HTTPException: 503 if database is not accessible.

    Example response:
        {"status": "healthy", "service": "database", "provider": "postgresql"}
    """
    try:
        # Execute a simple query to verify database connectivity
        await db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "database",
            "provider": "postgresql",
        }
    except Exception as exc:
        logger.error("database.health_check_failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not accessible",
        ) from exc


@router.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Readiness check for all application dependencies.

    Verifies that the application is ready to serve requests by checking
    all critical dependencies (database, configuration, etc.).

    Args:
        db: Database session dependency.

    Returns:
        dict: Readiness status with environment and dependency information.

    Raises:
        HTTPException: 503 if any dependency is not ready.

    Example response:
        {
            "status": "ready",
            "environment": "development",
            "database": "connected"
        }
    """
    settings = get_settings()

    try:
        # Verify database connectivity
        await db.execute(text("SELECT 1"))

        return {
            "status": "ready",
            "environment": settings.environment,
            "database": "connected",
        }
    except Exception as exc:
        logger.error("health.readiness_check_failed", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Application is not ready",
        ) from exc
