"""Quick smoke-test for the FinBERT Signal Sniper integration."""
import os
os.environ.setdefault("HUGGINGFACE_API_KEY", open(".env").read().split("HUGGINGFACE_API_KEY=")[1].split()[0])

from services.finbert_service import get_financial_sentiment

result = get_financial_sentiment("Solana ETF approved by SEC — institutional adoption incoming!")
print("FinBERT result:", result)
assert result is not None and "bullish" in result, "Expected bullish/bearish/neutral dict"
print("PASS ✓  bullish=%.2f  bearish=%.2f  neutral=%.2f" % (result["bullish"], result["bearish"], result["neutral"]))
