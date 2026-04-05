"""
HuggingFace Service — Zero-shot quality scoring for agent outputs.

Uses facebook/bart-large-mnli zero-shot classification to evaluate
whether agent output is excellent/good/adequate/poor for the task.

Score mapping:
  "excellent and comprehensive" → 9.5/10
  "good and relevant"           → 7.5/10
  "adequate but incomplete"     → 5.0/10
  "poor and off-topic"          → 2.5/10

Graceful contract:
  • Returns None on any failure → quality_service falls back to DeepSeek scoring
  • Synchronous — call via asyncio.to_thread from async context
  • Input truncated to 512 chars (BART model limit)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger("swarmpay.hf")

HF_KEY = os.environ.get("HUGGINGFACE_API_KEY", "").strip()

_LABELS = [
    "excellent and comprehensive",
    "good and relevant",
    "adequate but incomplete",
    "poor and off-topic",
]

# 0-10 scale to match existing quality_service scoring
_SCORE_MAP: dict[str, float] = {
    "excellent and comprehensive": 9.5,
    "good and relevant":           7.5,
    "adequate but incomplete":     5.0,
    "poor and off-topic":          2.5,
}

_TRUNCATE = 512
_HYPOTHESIS = "This response is {} for the given task."


def score_output(agent_output: str, task_description: str = "") -> Optional[float]:
    """
    Score agent output quality 0-10 using HuggingFace zero-shot classification.
    Returns float 0-10 or None on failure (caller uses DeepSeek fallback).
    Synchronous — call via asyncio.to_thread.
    """
    if not HF_KEY:
        logger.debug("[hf] HUGGINGFACE_API_KEY not set — skipping")
        return None

    text = (agent_output or "").strip()[:_TRUNCATE]
    if not text:
        return None

    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=HF_KEY)

        # huggingface_hub >= 0.20: signature is zero_shot_classification(text, candidate_labels, ...)
        # Returns list of ZeroShotClassificationOutputElement sorted by score descending
        result = client.zero_shot_classification(
            text,
            _LABELS,
            hypothesis_template=_HYPOTHESIS,
            multi_label=False,
        )

        # result is list[ZeroShotClassificationOutputElement] with .label and .score
        top_label = ""
        if result and isinstance(result, list):
            first = result[0]
            top_label = getattr(first, "label", "") or (first.get("label", "") if isinstance(first, dict) else "")
        elif hasattr(result, "labels"):
            labels_list = result.labels or []  # type: ignore[attr-defined]
            top_label = labels_list[0] if labels_list else ""
        score = _SCORE_MAP.get(top_label, 5.0)

        logger.info("[hf] quality score=%.1f top_label=%s", score, top_label)
        return score

    except Exception as exc:
        logger.warning("[hf] scoring failed: %s", exc)
        return None
