import pytest
import logging

logger = logging.getLogger(__name__)

@pytest.fixture(autouse=True)
async def cleanup_database_engine():
    """
    Autouse fixture to dispose of the async SQLAlchemy engine at the end of each test.
    This releases all pooled sockets and prevents ProactorEventLoop reuse errors on Windows.
    """
    yield
    try:
        from app.database import engine
        logger.info("Disposing of SQLAlchemy database engine connection pool...")
        await engine.dispose()
        logger.info("SQLAlchemy database engine disposed successfully.")
    except Exception as e:
        logger.warning(f"Failed to dispose SQLAlchemy engine: {e}")
