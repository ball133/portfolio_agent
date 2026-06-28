
import json
import os
from datetime import date
from tools.alerts import get_technical_score


def _get_thesis_state_file():
    return os.environ.get("THESIS_STATE_FILE", "state/thesis_state.json")


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
    if os.path.exists(_get_thesis_state_file()):
        with open(_get_thesis_state_file()) as f:
            return json.load(f)
    return {}


def _save_thesis_state(state: dict):
    os.makedirs("state", exist_ok=True)
    with open(_get_thesis_state_file(), "w") as f:
        json.dump(state, f, indent=2)


def _persist(state: dict, ticker: str,
             status: str, today: str,
             watch_streak: int = 0) -> str:
    state[ticker] = {
        "status": status,
        "updated": today,
        "watch_streak": watch_streak,
    }
    _save_thesis_state(state)
    return status


def _score_news(headlines: list,
                keywords: list) -> int:
    return sum(
        1 for h in headlines
        if any(k in h.lower() for k in keywords)
    )


def evaluate_thesis(
    ticker: str,
    tag: str,
    technical: dict,
    news_headlines: list,
    critic_narrative: str = ""
) -> str:
    """
    Evaluate thesis_status for a single position.
    Returns: "Intact", "Watch", or "Broken".
    Persists watch_streak counter to thesis_state.json.
    """
    state = _load_thesis_state()
    today = date.today().isoformat()
    prev = state.get(ticker, {})
    prev_status = prev.get("status", "Intact")
    watch_streak = prev.get("watch_streak", 0)

    # If already Broken, stay Broken unless there's a strong reason to change
    if prev_status == "Broken":
        # Check for intact keywords to possibly restore
        if critic_narrative:
            low = critic_narrative.lower()
            if sum(1 for k in INTACT_KEYWORDS if k in low) >= 2:
                return _persist(state, ticker, "Intact", today, 0)
        # Otherwise, stay Broken
        return _persist(state, ticker, "Broken", today, 0)

    # Tag overrides — no evaluation needed
    if tag in ("DEAD_WEIGHT", "LEVERAGED"):
        return _persist(state, ticker, "Broken", today, 0)

    # BROKEN conditions
    # B1: 4/4 bearish AND below MA200
    if (technical.get("score", 0) == 4 and
            not technical.get("price_bullish", True)):
        return _persist(state, ticker, "Broken", today, 0)

    # B2: critic narrative has 2+ broken keywords
    if critic_narrative:
        low = critic_narrative.lower()
        if sum(1 for k in BROKEN_KEYWORDS
               if k in low) >= 2:
            return _persist(
                state, ticker, "Broken", today, 0)

    # B3: Watch streak hit 3 consecutive sessions
    if prev_status == "Watch" and watch_streak >= 2:
        return _persist(state, ticker, "Broken", today, 0)

    # WATCH conditions
    # W1: technical score ≥3/4 bearish
    # SATELLITE: requires 4/4 to flip Watch on
    # technicals alone (narrative must confirm for 3/4)
    tech_watch_threshold = 3 \
        if tag == "CORE" else 4
    if technical.get("score", 0) >= tech_watch_threshold:
        streak = watch_streak + 1 \
            if prev_status == "Watch" else 1
        return _persist(
            state, ticker, "Watch", today, streak)

    # W2: RSI <40 AND MACD bearish simultaneously
    if (technical.get("rsi", 50) < 40 and
            technical.get("macd_bearish", False)):
        streak = watch_streak + 1 \
            if prev_status == "Watch" else 1
        return _persist(
            state, ticker, "Watch", today, streak)

    # W3: 2+ negative news AND already in Watch/Broken
    if (_score_news(news_headlines, BROKEN_KEYWORDS) >= 2
            and prev_status in ("Watch", "Broken")):
        streak = watch_streak + 1 \
            if prev_status == "Watch" else 1
        return _persist(
            state, ticker, "Watch", today, streak)

    # INTACT conditions
    # I1: price above MA20 AND RSI >50
    if (technical.get("rsi", 0) > 50 and
            not technical.get("price_bearish", True)):
        return _persist(
            state, ticker, "Intact", today, 0)

    # I2: critic confirms thesis (2+ intact keywords)
    if critic_narrative:
        low = critic_narrative.lower()
        if sum(1 for k in INTACT_KEYWORDS
               if k in low) >= 2:
            return _persist(
                state, ticker, "Intact", today, 0)

    # Default: carry forward previous status
    return _persist(
        state, ticker, prev_status, today, watch_streak)


def evaluate_all_thesis(
    position_tags: list,
    technicals: dict,
    news_map: dict,
    critic_narrative: str = ""
) -> list:
    """
    Evaluate thesis for all positions.
    Returns position_tags list with thesis_status added.
    """
    result = []
    for pos in position_tags:
        ticker = pos["ticker"]
        tag = pos["tag"]
        tech = technicals.get(ticker, {})
        news = news_map.get(ticker, [])
        status = evaluate_thesis(
            ticker, tag, tech, news, critic_narrative)
        result.append({**pos, "thesis_status": status})
    return result
