
import json
import os
from datetime import date, datetime
from tools.alerts import get_technical_score, get_bullish_score

THESIS_STATE_FILE = "state/thesis_state.json"

BROKEN_KEYWORDS = [
    "headwinds", "slowing", "losing share",
    "disappointing", "guidance cut", "margin pressure",
    "revenue miss", "losing momentum", "structural decline"
]
INTACT_KEYWORDS = [
    "beat", "strong demand", "record revenue",
    "expanding margin", "AI demand", "data center",
    "inference growth", "market share gain"
]


def _load_thesis_state() -> dict:
    if os.path.exists(THESIS_STATE_FILE):
        with open(THESIS_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_thesis_state(state: dict):
    os.makedirs("state", exist_ok=True)
    with open(THESIS_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _persist(state: dict, ticker: str, status: str, today: str, watch_streak: int = 0) -> str:
    state[ticker] = {
        "status": status,
        "watch_streak": watch_streak,
        "last_updated": today,
        "timestamp": datetime.now().isoformat()
    }
    _save_thesis_state(state)
    return status


def evaluate_thesis(
    ticker: str,
    tag: str,
    technical: dict,
    news_headlines: list[str],
    critic_narrative: str = ""
) -> str:
    """
    Returns: "Intact", "Watch", or "Broken"
    Persists watch streak counter in thesis_state.json.
    DEAD_WEIGHT and LEVERAGED always return "Broken".
    """
    state = _load_thesis_state()
    today = date.today().isoformat()

    # Tag overrides — no evaluation needed
    if tag == "DEAD_WEIGHT":
        return _persist(state, ticker, "Broken", today)
    if tag == "LEVERAGED":
        return _persist(state, ticker, "Broken", today)

    prev = state.get(ticker, {})
    prev_status = prev.get("status", "Intact")
    watch_streak = prev.get("watch_streak", 0)

    # ── BROKEN conditions ──────────────────────────────
    # B1: below MA200 AND 4/4 bearish
    if (technical.get("score", 0) == 4 and
            not technical.get("price_bullish", True)):
        return _persist(state, ticker, "Broken", today, 0)

    # B2: critic narrative says mandate broken
    if critic_narrative:
        low = critic_narrative.lower()
        if any(k in low for k in BROKEN_KEYWORDS):
            broken_hits = sum(
                1 for k in BROKEN_KEYWORDS if k in low)
            if broken_hits >= 2:
                return _persist(
                    state, ticker, "Broken", today, 0)

    # B3: three consecutive Watch sessions
    if prev_status == "Watch" and watch_streak >= 2:
        return _persist(state, ticker, "Broken", today, 0)

    # ── WATCH conditions ───────────────────────────────
    # W1: technical score 3/4 bearish
    if technical.get("score", 0) >= 3:
        new_streak = watch_streak + 1 if prev_status == "Watch" else 1
        return _persist(
            state, ticker, "Watch", today, new_streak)

    # W2: RSI < 40 AND MACD bearish simultaneously
    if (technical.get("rsi", 50) < 40 and
            technical.get("macd_bearish", False)):
        new_streak = watch_streak + 1 if prev_status == "Watch" else 1
        return _persist(
            state, ticker, "Watch", today, new_streak)

    # W3: negative news 2 sessions in a row (check today)
    neg_news_count = 0
    for headline in news_headlines:
        low_headline = headline.lower()
        if any(k in low_headline for k in BROKEN_KEYWORDS):
            neg_news_count += 1
    if neg_news_count >= 1:
        new_streak = watch_streak + 1 if prev_status == "Watch" else 1
        return _persist(
            state, ticker, "Watch", today, new_streak)

    # ── INTACT conditions (default) ────────────────────
    return _persist(state, ticker, "Intact", today, 0)
