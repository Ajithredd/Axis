"""
LangSmith Tracing Service — End-to-end observability for the Axis RAG pipeline.

Provides thin wrappers around the LangSmith SDK for creating parent traces and
child spans per pipeline stage. Gracefully no-ops if LANGSMITH_API_KEY is unset.

Usage:
    async with pipeline_trace(query=query, project_id=str(pid)) as trace:
        async with trace.span("retrieval") as span:
            results = await hybrid_search(...)
            span.set_outputs({"count": len(results)})
        trace.set_ragas_scores(ragas_metrics)
"""

import logging
import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _is_tracing_enabled() -> bool:
    """Check if LangSmith tracing is configured and enabled."""
    from app.config import settings
    has_key = bool(settings.langsmith_api_key)
    # Auto-enable if key is present, respecting explicit disable
    return has_key or settings.langsmith_enabled


def _setup_langsmith_env() -> None:
    """Set LangSmith environment variables from our settings."""
    from app.config import settings
    if settings.langsmith_api_key:
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")


class _NoOpSpan:
    """A no-op span that silently discards all operations when tracing is disabled."""

    def set_outputs(self, outputs: Dict[str, Any]) -> None:
        pass

    def set_metadata(self, metadata: Dict[str, Any]) -> None:
        pass

    def set_error(self, error: str) -> None:
        pass


class _NoOpTrace:
    """A no-op trace that silently discards all operations when tracing is disabled."""

    @asynccontextmanager
    async def span(self, name: str, inputs: Optional[Dict[str, Any]] = None):
        yield _NoOpSpan()

    def set_ragas_scores(self, ragas_metrics: Any) -> None:
        pass

    def set_outputs(self, outputs: Dict[str, Any]) -> None:
        pass


class LangSmithSpan:
    """Wraps a LangSmith RunTree child span."""

    def __init__(self, run):
        self._run = run

    def set_outputs(self, outputs: Dict[str, Any]) -> None:
        try:
            self._run.end(outputs=outputs)
            self._run.post()
        except Exception as e:
            logger.debug(f"[LangSmith] Failed to set span outputs: {e}")

    def set_metadata(self, metadata: Dict[str, Any]) -> None:
        try:
            self._run.extra = {**(self._run.extra or {}), **metadata}
        except Exception as e:
            logger.debug(f"[LangSmith] Failed to set span metadata: {e}")

    def set_error(self, error: str) -> None:
        try:
            self._run.end(error=error)
            self._run.post()
        except Exception as e:
            logger.debug(f"[LangSmith] Failed to set span error: {e}")


class LangSmithTrace:
    """Wraps a LangSmith RunTree parent trace for the full RAG pipeline."""

    def __init__(self, run):
        self._run = run

    @asynccontextmanager
    async def span(self, name: str, inputs: Optional[Dict[str, Any]] = None):
        """Create a child span for a pipeline sub-stage."""
        child_run = None
        try:
            child_run = self._run.create_child(
                name=name,
                run_type="chain",
                inputs=inputs or {},
            )
            child_run.post()
            span = LangSmithSpan(child_run)
            yield span
        except Exception as e:
            logger.debug(f"[LangSmith] Child span '{name}' failed: {e}")
            yield _NoOpSpan()
        finally:
            if child_run:
                try:
                    child_run.patch()
                except Exception:
                    pass

    def set_ragas_scores(self, ragas_metrics: Any) -> None:
        """Attach RAGAS evaluation scores as metadata to this trace."""
        try:
            from app.services.evaluation import RAGASMetrics
            if isinstance(ragas_metrics, RAGASMetrics):
                scores = {
                    "ragas_faithfulness": ragas_metrics.faithfulness,
                    "ragas_answer_relevancy": ragas_metrics.answer_relevancy,
                    "ragas_context_precision": ragas_metrics.context_precision,
                    "ragas_context_recall": ragas_metrics.context_recall,
                    "ragas_context_entity_recall": ragas_metrics.context_entity_recall,
                    "ragas_score": ragas_metrics.ragas_score,
                    "ragas_evaluated": ragas_metrics.evaluated,
                }
                self._run.extra = {**(self._run.extra or {}), "ragas": scores}
                self._run.patch()
        except Exception as e:
            logger.debug(f"[LangSmith] Failed to attach RAGAS scores: {e}")

    def set_outputs(self, outputs: Dict[str, Any]) -> None:
        try:
            self._run.end(outputs=outputs)
            self._run.patch()
        except Exception as e:
            logger.debug(f"[LangSmith] Failed to set trace outputs: {e}")


@asynccontextmanager
async def pipeline_trace(
    query: str,
    project_id: str,
    session_id: Optional[str] = None,
):
    """
    Context manager that creates a LangSmith parent trace for a full RAG pipeline run.

    Usage:
        async with pipeline_trace(query=query, project_id=str(pid)) as trace:
            async with trace.span("retrieval") as span:
                ...
                span.set_outputs({"count": 5})
    """
    if not _is_tracing_enabled():
        yield _NoOpTrace()
        return

    _setup_langsmith_env()

    run = None
    try:
        from langsmith.run_trees import RunTree
        from app.config import settings

        run = RunTree(
            name="axis-rag-pipeline",
            run_type="chain",
            project_name=settings.langsmith_project,
            inputs={
                "query": query,
                "project_id": project_id,
                "session_id": session_id or "",
            },
        )
        run.post()
        trace = LangSmithTrace(run)
        logger.info(f"[LangSmith] Trace started: {run.id}")
        yield trace
    except Exception as e:
        logger.warning(f"[LangSmith] Failed to start trace: {e}. Continuing without tracing.")
        yield _NoOpTrace()
    finally:
        if run:
            try:
                run.patch()
            except Exception:
                pass
