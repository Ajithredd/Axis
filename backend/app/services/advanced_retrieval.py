"""
Advanced Retrieval Strategies for the Axis RAG Pipeline.

Implements three advanced retrieval techniques that layer on top of the
existing hybrid search + RRF baseline:

1. Step-Back Prompting
   Generates a more abstract, high-level version of the user query before
   retrieval. Both the original and step-back queries are retrieved in
   parallel, then fused. Improves recall for overly specific queries.

2. Contextual Compression
   After reranking, low-scoring chunks are passed through an LLM that
   extracts only the sentences directly relevant to the query. Reduces
   context window noise sent to the final generation step.

3. Parent-Document Retrieval (Small-to-Big)
   When a small child chunk is retrieved as highly relevant, the system
   automatically expands to its full parent document chunk for richer
   context. Uses the parent_event_id metadata stored during ingestion.
"""

import logging
import re
from typing import Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)


# ─── 1. Step-Back Prompting ──────────────────────────────────────────────────

async def generate_step_back_query(
    query: str,
    client: Any,  # google.genai.Client
    model: str,
) -> Optional[str]:
    """
    Generate a more abstract, "step-back" version of the user query.

    Step-back prompting asks the LLM to rephrase the question at a higher
    level of abstraction. For example:
      Original: "Why was the payment gateway switched from Stripe to PayPal in v2.3?"
      Step-back: "What were the payment gateway decisions made for this project?"

    This broader query often retrieves relevant background context that the
    original specific query would miss.

    Returns:
        A single step-back query string, or None if generation failed.
    """
    from app.config import settings
    if not settings.step_back_prompting_enabled:
        return None

    prompt = (
        "You are an expert at reformulating questions for better information retrieval.\n"
        "Given the following specific question, generate ONE more abstract, higher-level version "
        "that would help retrieve relevant background context and principles.\n"
        "The step-back question should be broader but still relevant to the topic.\n"
        "Output ONLY the step-back question. No preamble, no explanation.\n\n"
        f"Original Question: {query}\n"
        "Step-Back Question:"
    )

    try:
        from app.services.chat import generate_content_with_retry
        response = await generate_content_with_retry(
            client=client,
            model=model,
            contents=prompt,
        )
        step_back = response.text.strip().strip('"\'')
        # Basic sanity check — must be a non-trivial question
        if step_back and len(step_back) > 10 and step_back != query:
            logger.info(f"[StepBack] '{query}' → '{step_back}'")
            return step_back
    except Exception as e:
        logger.warning(f"[StepBack] Step-back query generation failed: {e}")

    return None


# ─── 2. Contextual Compression ────────────────────────────────────────────────

async def compress_chunk(
    query: str,
    chunk_title: str,
    chunk_content: str,
    client: Any,  # google.genai.Client
    model: str,
) -> str:
    """
    Compress a retrieved chunk to extract only the sentences relevant to the query.

    Uses the LLM to act as a compressor: given the query and a full chunk,
    it returns only the sentences that are directly useful for answering the query.
    If nothing is relevant, returns an empty string.

    Args:
        query: The user's question.
        chunk_title: Title of the source chunk.
        chunk_content: Full text content of the chunk.
        client: Gemini API client.
        model: Model name to use for compression.

    Returns:
        Compressed text containing only the relevant sentences, or original
        content if compression fails or reduces content too aggressively.
    """
    if not chunk_content or len(chunk_content) < 100:
        return chunk_content  # Too short to compress meaningfully

    prompt = (
        "You are a context compression assistant.\n"
        "Given a User Query and a Source Document, extract ONLY the sentences from the document "
        "that are directly relevant to answering the query.\n"
        "Do NOT summarize or paraphrase. Copy exact sentences.\n"
        "If no sentences are relevant, output exactly: NO_RELEVANT_CONTENT\n\n"
        f"User Query: {query}\n\n"
        f"Source Document [{chunk_title}]:\n{chunk_content[:2000]}\n\n"
        "Relevant sentences:"
    )

    try:
        from app.services.chat import generate_content_with_retry
        response = await generate_content_with_retry(
            client=client,
            model=model,
            contents=prompt,
        )
        compressed = response.text.strip()

        if compressed == "NO_RELEVANT_CONTENT" or not compressed:
            return ""  # Signal that this chunk has nothing useful

        # If compression barely reduced the size, return original to avoid overhead
        if len(compressed) >= len(chunk_content) * 0.9:
            return chunk_content

        logger.debug(
            f"[Compression] '{chunk_title}': {len(chunk_content)} → {len(compressed)} chars "
            f"({100 * len(compressed) // max(len(chunk_content), 1)}% of original)"
        )
        return compressed

    except Exception as e:
        logger.warning(f"[Compression] Failed to compress chunk '{chunk_title}': {e}")
        return chunk_content  # Fallback to original


async def apply_contextual_compression(
    query: str,
    candidates: List[Any],  # List[SearchResult]
    rerank_scores: List[float],
    client: Any,
    model: str,
    threshold: float = 0.6,
) -> Tuple[List[Any], int]:
    """
    Apply contextual compression to candidates with low rerank scores.

    Chunks scoring below `threshold` are compressed by the LLM to extract
    only the relevant sentences. High-scoring chunks are kept as-is since
    they are already highly relevant.

    Args:
        query: The user's search query.
        candidates: List of SearchResult objects (post-reranking).
        rerank_scores: Corresponding rerank scores for each candidate.
        client: Gemini API client.
        model: Model name to use for compression.
        threshold: Rerank score below which compression is applied.

    Returns:
        Tuple of (modified candidates list, number of chunks compressed).
    """
    from app.config import settings
    if not settings.contextual_compression_enabled:
        return candidates, 0

    import asyncio
    from dataclasses import replace as dc_replace

    compressed_count = 0
    # Pad rerank_scores if shorter than candidates (fallback to threshold-1 to compress)
    scores = list(rerank_scores) + [0.0] * (len(candidates) - len(rerank_scores))

    async def _compress_one(idx: int, cand: Any, score: float):
        nonlocal compressed_count
        if score < threshold and cand.content:
            compressed = await compress_chunk(
                query=query,
                chunk_title=cand.title or "Untitled",
                chunk_content=cand.content,
                client=client,
                model=model,
            )
            if compressed and compressed != cand.content:
                compressed_count += 1
                # Return a new SearchResult with compressed content
                # SearchResult is a dataclass — use its fields
                from app.services.search import SearchResult
                return SearchResult(
                    node_id=cand.node_id,
                    project_id=cand.project_id,
                    node_type=cand.node_type,
                    content=compressed,
                    score=cand.score,
                    title=cand.title,
                    metadata={**(cand.metadata or {}), "compressed": True},
                    graph_context=cand.graph_context,
                )
        return cand

    tasks = [_compress_one(i, cand, scores[i]) for i, cand in enumerate(candidates)]
    results = await asyncio.gather(*tasks)
    # Filter out candidates whose entire content was compressed away
    final = [r for r in results if r.content]

    if compressed_count > 0:
        logger.info(f"[Compression] Compressed {compressed_count}/{len(candidates)} chunks")

    return final, compressed_count


# ─── 3. Parent-Document Retrieval ─────────────────────────────────────────────

async def expand_to_parent_documents(
    db: AsyncSession,
    candidates: List[Any],  # List[SearchResult]
) -> List[Any]:
    """
    Expand child chunk results to their parent documents for richer context.

    During ingestion, large documents are split into small child chunks for
    precise vector matching, but the parent document is stored with full content.
    When a child chunk matches well, its parent document is fetched to provide
    the LLM with broader context (the "Small-to-Big" retrieval pattern).

    Uses the `parent_event_id` field stored in chunk metadata during ingestion.

    Args:
        db: Async SQLAlchemy session.
        candidates: List of SearchResult objects.

    Returns:
        Modified list where child event chunks are replaced/supplemented by
        their parent document content.
    """
    from app.config import settings
    if not settings.parent_document_retrieval_enabled:
        return candidates

    from app.models.event import Event
    from app.services.search import SearchResult

    expanded = []
    seen_parent_ids = set()
    parent_expansions = 0

    for cand in candidates:
        # Only try to expand event-type nodes that have parent metadata
        if cand.node_type == "events" and cand.metadata:
            parent_id_str = cand.metadata.get("parent_event_id")
            if parent_id_str and parent_id_str not in seen_parent_ids:
                try:
                    import uuid
                    parent_id = uuid.UUID(parent_id_str)
                    stmt = select(Event).where(Event.id == parent_id)
                    db_res = await db.execute(stmt)
                    parent_event = db_res.scalar_one_or_none()

                    if parent_event and parent_event.content and len(parent_event.content) > len(cand.content):
                        seen_parent_ids.add(parent_id_str)
                        parent_expansions += 1
                        # Replace the child chunk with the richer parent document
                        expanded.append(SearchResult(
                            node_id=parent_id,
                            project_id=cand.project_id,
                            node_type="events",
                            content=parent_event.content,
                            score=cand.score,  # Keep child's relevance score
                            title=parent_event.title or cand.title,
                            metadata={
                                **(cand.metadata or {}),
                                "expanded_from_child": str(cand.node_id),
                                "parent_document": True,
                            },
                            graph_context=cand.graph_context,
                        ))
                        continue  # Skip adding the child chunk separately
                except Exception as e:
                    logger.warning(f"[ParentDoc] Failed to fetch parent {parent_id_str}: {e}")

        expanded.append(cand)

    if parent_expansions > 0:
        logger.info(f"[ParentDoc] Expanded {parent_expansions} child chunks to parent documents")

    return expanded
