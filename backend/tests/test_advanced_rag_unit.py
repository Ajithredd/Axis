import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel
from sqlalchemy import func
from google.genai import types

from app.config import settings
from app.services.embedding import chunk_text
from app.services.chat import (
    expand_query_via_llm,
    rerank_results_via_llm,
    evaluate_retrieval_results,
    ChatCitation,
    RAGMetrics,
)
from app.services.search import keyword_search_postgres, SearchResult


def test_child_chunking_settings():
    """Verify that settings contain the child chunk configurations and chunk_text respects them."""
    assert settings.child_chunk_size == 250
    assert settings.child_chunk_overlap == 50

    sample_text = "Hello world. " * 30  # ~390 characters
    chunks = chunk_text(sample_text, chunk_size=settings.child_chunk_size, chunk_overlap=settings.child_chunk_overlap)
    
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= settings.child_chunk_size


@pytest.mark.asyncio
async def test_expand_query_via_llm():
    """Test that query expansion correctly cleans and parses LLM outputs."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock()
    
    mock_response = MagicMock()
    mock_response.text = "1. docker container issues\n- postgres connection pool\n* database timeout"
    mock_client.aio.models.generate_content.return_value = mock_response

    queries = await expand_query_via_llm("db connection issue", mock_client, "gemini-2.5-flash")
    
    assert len(queries) == 3
    assert queries[0] == "docker container issues"
    assert queries[1] == "postgres connection pool"
    assert queries[2] == "database timeout"


@pytest.mark.asyncio
async def test_rerank_results_via_llm():
    """Test that LLM-based reranking correctly reorders candidate SearchResults."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock()
    
    # Mock RerankResponse — candidate index 2 gets the highest score
    mock_response = MagicMock()
    mock_response.text = '{"scores": [{"index": 0, "relevance_score": 0.2}, {"index": 1, "relevance_score": 0.5}, {"index": 2, "relevance_score": 0.95}, {"index": 3, "relevance_score": 0.1}]}'
    mock_client.aio.models.generate_content.return_value = mock_response

    project_id = uuid.uuid4()
    candidates = []
    for i in range(4):
        candidates.append(SearchResult(
            node_id=uuid.uuid4(),
            project_id=project_id,
            node_type="requirements",
            content=f"Document {i} content about topic {i}",
            score=0.5 - i * 0.1,
            title=f"Doc {i}"
        ))

    reranked, scores = await rerank_results_via_llm(
        query="important topic",
        candidates=candidates,
        client=mock_client,
        model="gemini-2.5-flash",
        top_k=3
    )

    assert len(reranked) == 3
    assert len(scores) == 3
    # Candidate index 2 (score 0.95) should be first
    assert reranked[0].node_id == candidates[2].node_id
    # Candidate index 1 (score 0.5) should be second
    assert reranked[1].node_id == candidates[1].node_id
    # Scores should be sorted descending
    assert scores[0] >= scores[1] >= scores[2]


@pytest.mark.asyncio
async def test_fts_query_syntax():
    """Verify that keyword_search_postgres constructs queries using full-text search functions."""
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.all.return_value = []
    mock_db.execute.return_value = mock_res
    
    project_id = uuid.uuid4()
    await keyword_search_postgres(
        db=mock_db,
        query="authentication sso",
        project_id=project_id,
        limit=5,
        node_types=["requirements"]
    )
    
    assert mock_db.execute.called
    stmt = mock_db.execute.call_args[0][0]
    
    # Check that SQLAlchemy compiled SQL statement contains full-text search operators
    stmt_str = str(stmt).lower()
    assert "ts_rank_cd" in stmt_str
    assert "to_tsvector" in stmt_str
    assert "websearch_to_tsquery" in stmt_str
    assert "setweight" in stmt_str


def test_rag_metrics_dataclass():
    """Verify RAGMetrics dataclass initializes and serializes correctly."""
    from dataclasses import asdict

    metrics = RAGMetrics()
    d = asdict(metrics)

    # All latency fields should default to 0.0
    assert d["total_latency_s"] == 0.0
    assert d["query_expansion_latency_s"] == 0.0
    assert d["retrieval_latency_s"] == 0.0
    assert d["reranking_latency_s"] == 0.0
    assert d["agentic_loop_latency_s"] == 0.0
    assert d["generation_latency_s"] == 0.0

    # Retrieval quality
    assert d["expanded_query_count"] == 0
    assert d["total_candidates_retrieved"] == 0
    assert d["unique_candidates_after_merge"] == 0
    assert d["candidates_after_reranking"] == 0
    assert d["rerank_scores"] == []
    assert d["rerank_mean_score"] == 0.0

    # Agentic
    assert d["agentic_tool_calls"] == 0
    assert d["agentic_loop_iterations"] == 0

    # Generation quality
    assert d["confidence_score"] == 0.0
    assert d["citation_count"] == 0
    assert d["context_sources_used"] == 0

    # Faithfulness proxy
    assert d["answer_length_chars"] == 0
    assert d["context_length_chars"] == 0
    assert d["context_utilization_ratio"] == 0.0

    # Verify mutation works
    metrics.total_latency_s = 1.234
    metrics.citation_count = 3
    metrics.context_sources_used = 5
    metrics.context_utilization_ratio = round(3 / 5, 4)
    d2 = asdict(metrics)
    assert d2["total_latency_s"] == 1.234
    assert d2["context_utilization_ratio"] == 0.6


def test_retrieval_evaluation_metrics():
    """Verify retrieval eval computes common ranking metrics from candidate overlap."""
    project_id = uuid.uuid4()
    candidates = [
        SearchResult(
            node_id=uuid.uuid4(),
            project_id=project_id,
            node_type="requirements",
            content="Authentication flow for SSO login",
            score=0.9,
            title="SSO authentication",
        ),
        SearchResult(
            node_id=uuid.uuid4(),
            project_id=project_id,
            node_type="events",
            content="Weekly planning update",
            score=0.6,
            title="Sprint planning",
        ),
        SearchResult(
            node_id=uuid.uuid4(),
            project_id=project_id,
            node_type="decisions",
            content="Decision to improve authentication retry logic",
            score=0.7,
            title="Auth retry decision",
        ),
    ]

    metrics = evaluate_retrieval_results("authentication sso", candidates, top_k=3)

    assert metrics["precision_at_k"] > 0
    assert metrics["recall_at_k"] > 0
    assert metrics["hit_rate_at_k"] == 1.0
    assert metrics["mrr"] == 1.0
    assert metrics["ndcg"] > 0
    assert metrics["relevant_count"] >= 1
