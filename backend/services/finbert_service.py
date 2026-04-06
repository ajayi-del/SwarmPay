"""
FinBERT Service — Real-time Financial Sentiment Analysis

Queries the free HuggingFace ProsusAI/finbert model to determine if market 
context is Bullish, Bearish, or Neutral.
Integrated directly into the CIPHER agent as part of the "Signal Sniper" setup.
"""

import logging
import os
from typing import Optional, Dict

logger = logging.getLogger("swarmpay.finbert")

HF_KEY = os.environ.get("HUGGINGFACE_API_KEY", "").strip()
MODEL_ID = "ProsusAI/finbert"
_TRUNCATE = 512  # FinBERT has a 512 token limit

def get_financial_sentiment(text: str) -> Optional[Dict[str, float]]:
    """
    Returns sentiment percentages: {"bullish": 0.85, "bearish": 0.05, "neutral": 0.10}
    Synchronous — call via asyncio.to_thread.
    """
    if not HF_KEY:
        logger.debug("[finbert] HUGGINGFACE_API_KEY not set — skipping")
        return None

    clean_text = (text or "").strip()[:_TRUNCATE]
    if not clean_text:
        return None

    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(token=HF_KEY)

        # FinBERT is a text classification model
        result = client.text_classification(clean_text, model=MODEL_ID)
        
        # Result is list of dicts or objects, usually:
        # [{"label": "positive", "score": 0.85}, {"label": "negative", "score": 0.05}, {"label": "neutral", "score": 0.10}]
        # Map them to bullish/bearish/neutral

        output = {"bullish": 0.0, "bearish": 0.0, "neutral": 0.0}
        
        # Safely parse the HuggingFace return structure
        if isinstance(result, list):
            for item in result:
                label = getattr(item, "label", "") or (item.get("label", "") if isinstance(item, dict) else "")
                score = getattr(item, "score", 0.0) or (item.get("score", 0.0) if isinstance(item, dict) else 0.0)
                
                l_lower = str(label).lower()
                if "positive" in l_lower:
                    output["bullish"] = score
                elif "negative" in l_lower:
                    output["bearish"] = score
                elif "neutral" in l_lower:
                    output["neutral"] = score

        logger.info("[finbert] score: %.2f bullish, %.2f bearish", output["bullish"], output["bearish"])
        return output

    except Exception as exc:
        logger.warning("[finbert] failed: %s", exc)
        return None
