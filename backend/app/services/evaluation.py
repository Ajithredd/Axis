"""
RAGAS Evaluation Service — Computes retrieval and generation quality metrics.

Uses RAGAS (Retrieval Augmented Generation Assessment) with Gemini as the LLM
judge to evaluate:
  - Faithfulness: Are answer claims grounded in the retrieved context?
  - Answer Relevancy: Does the answer address the original question?
  - Context Precision: Are the retrieved chunks actually relevant (signal vs noise)?
  - Context Recall: Does the retrieved context contain the answer?

All evaluation runs asynchronously and fire-and-forget after chat generation.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RAGASMetrics:
    """RAGAS evaluation scores for a single RAG pipeline call."""
    faithfulness: float = 0.0
    answer_relevancy: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    context_entity_recall: float = 0.0
    ragas_score: float = 0.0  # Harmonic mean of all enabled metrics
    evaluated: bool = False
    error: Optional[str] = None


def _compute_harmonic_mean(scores: List[float]) -> float:
    """Compute harmonic mean, ignoring zero values."""
    non_zero = [s for s in scores if s > 0]
    if not non_zero:
        return 0.0
    return len(non_zero) / sum(1.0 / s for s in non_zero)


async def compute_ragas_metrics(
    query: str,
    answer: str,
    contexts: List[str],
    ground_truth: Optional[str] = None,
) -> RAGASMetrics:
    """
    Compute RAGAS metrics for a single RAG pipeline invocation.

    Args:
        query: The original user question.
        answer: The generated answer from the LLM.
        contexts: List of retrieved context chunks passed to the LLM.
        ground_truth: Optional reference answer (improves context_recall accuracy).

    Returns:
        RAGASMetrics dataclass with scores for each metric.
    """
    from app.config import settings

    if not settings.ragas_enabled:
        return RAGASMetrics(evaluated=False, error="RAGAS evaluation disabled in config")

    if not contexts:
        return RAGASMetrics(evaluated=False, error="No contexts provided for RAGAS evaluation")

    try:
        from ragas import evaluate, EvaluationDataset
        from ragas.metrics import (
            Faithfulness,
            AnswerRelevancy,
            ContextPrecision,
            ContextEntityRecall,
        )
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    except ImportError as e:
        logger.warning(f"RAGAS or langchain-google-genai not installed: {e}. Skipping evaluation.")
        return RAGASMetrics(evaluated=False, error=f"Import error: {e}")

    try:
        # Build RAGAS dataset sample
        sample = {
            "user_input": query,
            "response": answer,
            "retrieved_contexts": contexts,
        }
        if ground_truth:
            sample["reference"] = ground_truth

        dataset = EvaluationDataset.from_list([sample])

        # Set up Gemini as the RAGAS judge LLM
        llm = ChatGoogleGenerativeAI(
            model=settings.ragas_eval_model,
            google_api_key=settings.gemini_api_key,
            temperature=0.0,
        )
        embeddings = GoogleGenerativeAIEmbeddings(
            model=f"models/{settings.embedding_model}",
            google_api_key=settings.gemini_api_key,
        )
        ragas_llm = LangchainLLMWrapper(llm)
        ragas_embeddings = LangchainEmbeddingsWrapper(embeddings)

        # Select metrics — context_recall requires a reference/ground_truth
        metrics_to_run = [
            Faithfulness(llm=ragas_llm),
            AnswerRelevancy(llm=ragas_llm, embeddings=ragas_embeddings),
            ContextPrecision(llm=ragas_llm),
            ContextEntityRecall(llm=ragas_llm),
        ]
        if ground_truth:
            from ragas.metrics import ContextRecall
            metrics_to_run.append(ContextRecall(llm=ragas_llm))

        # Run RAGAS evaluation in a thread executor (RAGAS is sync internally)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: evaluate(dataset=dataset, metrics=metrics_to_run)
        )

        scores_df = result.to_pandas()
        row = scores_df.iloc[0]

        faithfulness = float(row.get("faithfulness", 0.0) or 0.0)
        answer_relevancy = float(row.get("answer_relevancy", 0.0) or 0.0)
        context_precision = float(row.get("context_precision", 0.0) or 0.0)
        context_recall = float(row.get("context_recall", 0.0) or 0.0) if ground_truth else 0.0
        context_entity_recall = float(row.get("context_entity_recall", 0.0) or 0.0)

        active_scores = [s for s in [faithfulness, answer_relevancy, context_precision, context_entity_recall] if s > 0]
        ragas_score = _compute_harmonic_mean(active_scores)

        logger.info(
            f"[RAGAS] Faithfulness={faithfulness:.3f} | AnswerRelevancy={answer_relevancy:.3f} | "
            f"ContextPrecision={context_precision:.3f} | ContextEntityRecall={context_entity_recall:.3f} | "
            f"RAGAS Score={ragas_score:.3f}"
        )

        return RAGASMetrics(
            faithfulness=round(faithfulness, 4),
            answer_relevancy=round(answer_relevancy, 4),
            context_precision=round(context_precision, 4),
            context_recall=round(context_recall, 4),
            context_entity_recall=round(context_entity_recall, 4),
            ragas_score=round(ragas_score, 4),
            evaluated=True,
        )

    except Exception as e:
        logger.warning(f"[RAGAS] Evaluation failed: {e}")
        return RAGASMetrics(evaluated=False, error=str(e))
