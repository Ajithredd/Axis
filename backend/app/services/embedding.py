"""
Embedding service — text chunking + Google Gemini embedding generation.

Handles:
  1. Splitting long text into overlapping chunks
  2. Generating vector embeddings via Gemini text-embedding-004
  3. Deduplication via content hashing
"""

import hashlib
from typing import AsyncGenerator

from google import genai

from app.config import settings


# Initialize Gemini client
_gemini_client = genai.Client(api_key=settings.gemini_api_key)


def chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """
    Split text into overlapping chunks for embedding.

    Uses simple character-based splitting with overlap to maintain
    context across chunk boundaries.
    """
    if not text or not text.strip():
        return []

    size = chunk_size or settings.chunk_size
    overlap = chunk_overlap or settings.chunk_overlap
    text = text.strip()

    # Short text — no need to split
    if len(text) <= size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + size

        # Try to break at a paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start, end)
            if para_break > start + size // 2:
                end = para_break + 2
            else:
                # Look for sentence break
                for sep in [". ", ".\n", "! ", "? "]:
                    sent_break = text.rfind(sep, start, end)
                    if sent_break > start + size // 2:
                        end = sent_break + len(sep)
                        break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def content_hash(text: str) -> str:
    """Generate a SHA-256 hash of the text for deduplication."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def generate_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts using Google Gemini.

    Returns a list of embedding vectors (one per input text).
    """
    if not texts:
        return []

    result = _gemini_client.models.embed_content(
        model=f"models/{settings.embedding_model}",
        contents=texts,
    )

    return [emb.values for emb in result.embeddings]


async def generate_single_embedding(text: str) -> list[float]:
    """Generate an embedding for a single text string."""
    embeddings = await generate_embeddings([text])
    return embeddings[0] if embeddings else []
