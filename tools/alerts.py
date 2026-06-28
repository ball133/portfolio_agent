"""Portfolio alerting and sell signal engine."""
import os
import json
import yfinance as yf
from datetime import date, datetime
from config.settings import STATE_DIR

ALERTS_STATE_FILE = os.path.join(STATE_DIR, "alerts_state.json")


def _load_fired() -> dict:
    """Load fired alerts state from file."""
    if os.path.exists(ALERTS_STATE_FILE):
        with open(ALERTS_STATE_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}
    return {}


def _save_fired(state: dict) -> None:
    """Save fired alerts state to file."""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(ALERTS_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, default=str)


def evaluate_alerts(position_tags: list, holdings_prices: dict) -> list:
    """
    Evaluate monitoring alerts (placeholder for future implementation).
    Returns list of alert dicts.
    """
    # This is a placeholder - will be implemented in future tasks
    return []


def get_technical_score(ticker: str) -> dict:
    """
    Score 0-3: how many bearish technical conditions met.
    Returns individual factor results + total score.
    """
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if hist.empty or len(hist) < 26:
            return {"available": False, "score": 0}

        close = hist["Close"]
        volume = hist["Volume"]
        price = close.iloc[-1]

        # Factor 1: Price vs MAs
        ma20 = close.rolling(20).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1] if len(hist) >= 200 else ma20
        price_bearish = bool(price < ma20 and price < ma200)

        # Factor 2: MACD momentum
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = (ema12 - ema26).iloc[-1]
        signal = (ema12 - ema26).ewm(span=9).mean().iloc[-1]
        macd_bearish = bool(macd < 0 and macd < signal)

        # Factor 3: Volume trend (OBV direction)
        obv = (volume * (~(close.diff() < 0) * 2 - 1)).cumsum()
        obv_bearish = bool(obv.iloc[-1] < obv.rolling(10).mean().iloc[-1])

        # Factor 4: RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        rsi_bearish = bool(rsi < 45)

        score = sum([
            price_bearish,
            macd_bearish,
            obv_bearish,
            rsi_bearish
        ])

        return {
            "available": True,
            "price": round(float(price), 2),
            "score": score,  # 0-4
            "price_bearish": price_bearish,
            "macd_bearish": macd_bearish,
            "obv_bearish": obv_bearish,
            "rsi_bearish": rsi_bearish,
            "macd": round(float(macd), 3),
            "rsi": round(float(rsi), 1),
            "ma20": round(float(ma20), 2),
            "ma200": round(float(ma200), 2),
        }
    except Exception as e:
        return {"available": False, "score": 0, "error": str(e)}


# Sell threshold per tag
SELL_THRESHOLDS = {
    "CORE": 3,  # Need 3-of-4 for hard sell
    "SATELLITE": 2,  # 2-of-4 sufficient
    "PROBLEM": 1,  # Already deteriorating
    "DEAD_WEIGHT": 0,  # Always flag regardless
    "LEVERAGED": 0,  # Always flag regardless
}

SELL_LABELS = {
    0: None,
    1: ("WATCH", "⚪"),
    2: ("SELL CANDIDATE", "🟡"),
    3: ("HARD SELL", "🔴"),
    4: ("HARD SELL", "🔴"),
}


def get_sell_signals(position_tags: list, holdings_prices: dict) -> list:
    """
    Evaluate sell conditions for all positions.
    Returns list of sell signal dicts, strongest first.
    """
    fired_state = _load_fired()
    signals = []
    today = date.today().isoformat()

    for pos in position_tags:
        ticker = pos["ticker"]
        tag = pos["tag"]
        weight = pos.get("weight", 0)
        threshold = SELL_THRESHOLDS.get(tag, 2)
        tech = get_technical_score(ticker)

        if not tech.get("available") and tag not in ("DEAD_WEIGHT", "LEVERAGED"):
            continue

        score = tech.get("score", 0)
        # DEAD_WEIGHT and LEVERAGED always score max
        if tag in ("DEAD_WEIGHT", "LEVERAGED"):
            score = 4

        if score < threshold:
            continue

        label, emoji = SELL_LABELS.get(min(score, 4), (None, None))
        if not label:
            continue

        alert_key = f"{ticker}_{today}_sell_{label}"
        if alert_key in fired_state:
            continue

        # Build factor summary
        factors = []
        if tech.get("price_bearish"):
            factors.append(f"破MA20(${tech['ma20']:.0f}) 破MA200(${tech['ma200']:.0f})")
        if tech.get("macd_bearish"):
            factors.append(f"MACD {tech['macd']:+.2f} 偏空")
        if tech.get("obv_bearish"):
            factors.append("OBV下降 (分發中)")
        if tech.get("rsi_bearish"):
            factors.append(f"RSI {tech['rsi']:.0f} 偏弱")
        if tag == "DEAD_WEIGHT":
            factors.append("無AI主題論據")
        if tag == "LEVERAGED":
            factors.append("槓桿產品違反授權")

        factor_str = " | ".join(factors) if factors else "mandate violation"

        price = holdings_prices.get(ticker, {}).get("price", tech.get("price", 0))

        message = (
            f"{emoji} *{ticker} {label}*\n\n"
            f"📊 Tag: {tag} | Weight: {weight*100:.1f}%\n"
            f"💰 Price: ${price:.2f}\n"
            f"📉 Signals ({score}/4): {factor_str}\n\n"
        )

        if label == "HARD SELL":
            message += (
                f"🔴 *Action: EXIT or TRIM immediately*\n"
                f"Rationale: {score}/4 bearish factors confirmed — thesis deteriorating\n"
                f"Trigger: *Immediate*"
            )
        elif label == "SELL CANDIDATE":
            message += (
                f"🟡 *Action: REVIEW position*\n"
                f"Rationale: {score}/4 bearish factors — watch for 3rd confirmation\n"
                f"Trigger: If one more factor turns bearish"
            )

        signals.append({
            "ticker": ticker,
            "tag": tag,
            "score": score,
            "label": label,
            "priority": emoji,
            "message": message,
            "fire_key": alert_key
        })

        fired_state[alert_key] = {
            "fired_at": datetime.now().isoformat(),
            "score": score,
            "price": price
        }

    _save_fired(fired_state)
    # Sort: highest score first
    return sorted(signals, key=lambda x: x["score"], reverse=True)
