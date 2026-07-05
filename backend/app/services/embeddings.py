import logging
import asyncio
from typing import List, Optional
from google import genai
from google.genai.errors import APIError

from app.config import settings

logger = logging.getLogger(__name__)

class EmbeddingEngine:
    """Service to generate vector embeddings using Google Gemini API."""

    def __init__(self):
        # Initialize Google GenAI client
        self.api_key = settings.gemini_api_key
        if not self.api_key:
            logger.warning("gemini_api_key is not set in configuration. Embeddings will fail.")
        
        self.model = settings.embedding_model
        self._loop = None

    @property
    def client(self) -> genai.Client:
        """Get or create the genai.Client bound to the current running event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if not hasattr(self, "_client_instance") or self._loop != current_loop:
            self._client_instance = genai.Client(api_key=self.api_key)
            self._loop = current_loop
        return self._client_instance

    async def generate_embedding(self, text: str, retries: int = 3) -> Optional[List[float]]:
        """
        Generate an embedding for a single string.
        Includes a simple retry mechanism for rate limits (429) or transient errors.
        """
        if not text or not text.strip():
            return None

        for attempt in range(retries):
            try:
                # Using the async client
                response = await self.client.aio.models.embed_content(
                    model=self.model,
                    contents=text
                )
                if response.embeddings and len(response.embeddings) > 0:
                    return response.embeddings[0].values
                return None
            except APIError as e:
                if e.code == 429 or e.code >= 500:
                    logger.warning(f"Embedding API error (attempt {attempt + 1}/{retries}): {e}")
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)  # Exponential backoff
                        continue
                logger.error(f"Failed to generate embedding: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error during embedding generation: {e}")
                raise

        return None

    async def generate_batch_embeddings(self, texts: List[str], retries: int = 3) -> List[List[float]]:
        """
        Generate embeddings for a list of strings.
        The genai embed_content supports batching by passing a list of strings.
        """
        if not texts:
            return []

        # Filter out empty strings but keep track of indices to maintain order if necessary.
        # For simplicity, we assume texts are already filtered or we send them as is.
        valid_texts = [t if t.strip() else " " for t in texts]

        for attempt in range(retries):
            try:
                response = await self.client.aio.models.embed_content(
                    model=self.model,
                    contents=valid_texts
                )
                if response.embeddings:
                    return [emb.values for emb in response.embeddings]
                return []
            except APIError as e:
                if e.code == 429 or e.code >= 500:
                    logger.warning(f"Embedding batch API error (attempt {attempt + 1}/{retries}): {e}")
                    if attempt < retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                logger.error(f"Failed to generate batch embeddings: {e}")
                raise
            except Exception as e:
                logger.error(f"Unexpected error during batch embedding generation: {e}")
                raise
        return []

# Singleton instance
embedding_engine = EmbeddingEngine()
