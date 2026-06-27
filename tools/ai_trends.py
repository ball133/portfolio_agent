"""AI trend stocks retrieval function."""
from config.settings import AI_TREND_STOCKS


def get_ai_trend_stocks() -> dict:
    """Get a curated list of AI trend stocks to watch."""
    ai_trend_stocks = [
        {"ticker": stock["ticker"], "company": stock["company"], "reason": ""}
        for stock in AI_TREND_STOCKS
    ]
    # Add reasons (matching original code)
    ai_trend_stocks[0]["reason"] = "GPU leader, AI training hardware"
    ai_trend_stocks[1]["reason"] = "AI infrastructure solutions"
    ai_trend_stocks[2]["reason"] = "AI accelerators and CPUs"
    ai_trend_stocks[3]["reason"] = "Azure AI, Copilot, OpenAI partnership"
    ai_trend_stocks[4]["reason"] = "Google AI, DeepMind, cloud AI"
    ai_trend_stocks[5]["reason"] = "AI research, Llama models"
    ai_trend_stocks[6]["reason"] = "AI chip manufacturing"
    ai_trend_stocks[7]["reason"] = "AI for enterprise analytics"
    ai_trend_stocks[8]["reason"] = "AI data cloud platform"
    ai_trend_stocks[9]["reason"] = "Einstein AI, CRM AI integrations"

    return {"ai_trend_stocks": ai_trend_stocks, "success": True}
