"""Qdrant connection and initialization logic."""

import logging
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.config import settings

logger = logging.getLogger(__name__)

# Single instance of AsyncQdrantClient to be reused
_client: AsyncQdrantClient | None = None

def get_qdrant_client() -> AsyncQdrantClient:
    """Get or initialize the AsyncQdrantClient."""
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.qdrant_url)
    return _client

async def close_qdrant_client() -> None:
    """Close the Qdrant client connection."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None

async def init_qdrant_collections() -> None:
    """Ensure required collections exist in Qdrant."""
    client = get_qdrant_client()
    collections_to_create = ["requirements", "decisions", "events", "features", "stakeholders"]
    
    try:
        existing = await client.get_collections()
        existing_names = {c.name for c in existing.collections}
        
        for name in collections_to_create:
            if name not in existing_names:
                logger.info(f"Creating Qdrant collection: {name}")
                await client.create_collection(
                    collection_name=name,
                    vectors_config=models.VectorParams(
                        size=settings.embedding_dimensions,
                        distance=models.Distance.COSINE,
                    ),
                )
            else:
                logger.debug(f"Qdrant collection {name} already exists.")
    except Exception as e:
        logger.error(f"Failed to initialize Qdrant collections: {e}")
        # Allow app to start even if Qdrant is down, but log the error
