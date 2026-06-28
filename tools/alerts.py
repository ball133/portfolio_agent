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
        thesis = pos.get("thesis_status", "Unknown")
        base_threshold = SELL_THRESHOLDS.get(tag, 2)

        if tag in ("DEAD_WEIGHT", "LEVERAGED"):
            threshold = 0       # Always fires
        elif thesis == "Broken":
            threshold = base_threshold  # 3 for CORE, 2 for SAT
        elif thesis == "Watch":
            threshold = base_threshold + 1  # 4 for CORE, 3 for SAT
        elif thesis == "Intact":
            threshold = 99      # Never fires
        else:
            threshold = base_threshold
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

        # ── GUARD 1: 52-week low proximity ──────────────
        # Suppress if price is within 5% of 52w low.
        # Near-low = oversold exhaustion, not thesis break.
        try:
            _hist = yf.Ticker(ticker).history(period="1y")
            low_52w = _hist["Close"].min() \
                      if not _hist.empty else 0
            last_price = tech.get("price", 0)
            pct_from_low = (
                (last_price - low_52w) / low_52w * 100
                if low_52w > 0 else 99
            )
        except Exception:
            pct_from_low = 99
            _hist = None

        if (pct_from_low < 5 and
                tag not in ("DEAD_WEIGHT", "LEVERAGED")):
            signals.append({
                "ticker": ticker,
                "tag": tag,
                "score": score,
                "label": "SUPPRESSED",
                "priority": "⚪",
                "message": (
                    f"⚪ *{ticker} SELL SUPPRESSED*\n"
                    f"📊 Tag: {tag} | Weight: "
                    f"{weight*100:.1f}%\n"
                    f"💰 Price: ${last_price:.2f} "
                    f"({pct_from_low:.1f}% above 52w low "
                    f"${low_52w:.2f})\n"
                    f"⚠️ Near 52w low — oversold, "
                    f"not thesis break. Watching."
                ),
                "fire_key": None,
            })
            continue

        # ── GUARD 2: Recent strong rebound ───────────────
        # Suppress if last session returned > 3%.
        # Strong single-session rebound = reversal signal.
        try:
            if _hist is not None and len(_hist) >= 2:
                prev_close = _hist["Close"].iloc[-2]
                last_close = _hist["Close"].iloc[-1]
                session_return = (
                    (last_close - prev_close)
                    / prev_close * 100
                )
            else:
                session_return = 0
        except Exception:
            session_return = 0

        if (session_return > 3.0 and
                tag not in ("DEAD_WEIGHT", "LEVERAGED")):
            signals.append({
                "ticker": ticker,
                "tag": tag,
                "score": score,
                "label": "SUPPRESSED",
                "priority": "⚪",
                "message": (
                    f"⚪ *{ticker} SELL SUPPRESSED*\n"
                    f"📊 Tag: {tag} | Weight: "
                    f"{weight*100:.1f}%\n"
                    f"💰 Price: ${last_price:.2f} "
                    f"({session_return:+.1f}% last session)\n"
                    f"⚠️ Strong rebound detected — "
                    f"watching for 3rd confirmation "
                    f"next session."
                ),
                "fire_key": None,
            })
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
    return sorted(signals, key=lambda x: x["score"], reverse=True)

def get_bullish_score(ticker: str) -> dict:
    """
    Score 0-4: how many bullish technical conditions met.
    Mirror of get_technical_score() but inverted signals.
    """
    try:
        hist = yf.Ticker(ticker).history(period="1y")
        if hist.empty or len(hist) < 26:
            return {"available": False, "score": 0}

        close = hist["Close"]
        volume = hist["Volume"]
        price = close.iloc[-1]
        ma20 = close.rolling(20).mean().iloc[-1]
        ma200 = close.rolling(200).mean().iloc[-1] if len(hist) >= 200 else ma20

        # Factor 1: Price reclaimed both MAs
        price_bullish = bool(price > ma20 and price > ma200)

        # Factor 2: MACD crossover bullish
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        macd = (ema12 - ema26).iloc[-1]
        signal = (ema12 - ema26).ewm(span=9).mean().iloc[-1]
        macd_bullish = bool(macd > 0 and macd > signal)

        # Factor 3: OBV rising (accumulation)
        obv = (volume * (~(close.diff() < 0) * 2 - 1)).cumsum()
        obv_bullish = bool(obv.iloc[-1] > obv.rolling(10).mean().iloc[-1])

        # Factor 4: RSI recovering (40-65 sweet spot)
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        rsi_bullish = bool(40 < rsi < 70)

        score = sum([price_bullish, macd_bullish, obv_bullish, rsi_bullish])

        return {
            "available": True,
            "price": round(float(price), 2),
            "score": score,
            "price_bullish": price_bullish,
            "macd_bullish": macd_bullish,
            "obv_bullish": obv_bullish,
            "rsi_bullish": rsi_bullish,
            "macd": round(float(macd), 3),
            "rsi": round(float(rsi), 1),
            "ma20": round(float(ma20), 2),
            "ma200": round(float(ma200), 2),
            "pct_from_ma20": round((price - ma20) / ma20 * 100, 1),
        }
    except Exception as e:
        return {"available": False, "score": 0, "error": str(e)}


# Buy thresholds: SATELLITE needs 2/4, CORE needs 3/4
# (add to existing CORE, scale SATELLITE into CORE)
BUY_THRESHOLDS = {
    "CORE": 3,  # Add to winner on strength
    "SATELLITE": 2,  # Scale-up trigger
    "PROBLEM": 3,  # High bar — needs full recovery
    "DEAD_WEIGHT": 99,  # Never buy — exit first
    "LEVERAGED": 99,  # Never buy — exit first
}

BUY_LABELS = {
    0: None,
    1: ("WATCH", "⚪"),
    2: ("BUY CANDIDATE", "🟢"),
    3: ("STRONG BUY", "💚"),
    4: ("STRONG BUY", "💚"),
}


def get_buy_signals(position_tags: list, holdings_prices: dict) -> list:
    """
    Evaluate buy/scale-up conditions for all positions.
    DEAD_WEIGHT and LEVERAGED are never surfaced.
    Returns list sorted by score descending.
    """
    fired_state = _load_fired()
    signals = []
    today = date.today().isoformat()

    for pos in position_tags:
        ticker = pos["ticker"]
        tag = pos["tag"]
        weight = pos.get("weight", 0)
        threshold = BUY_THRESHOLDS.get(tag, 99)

        # Never generate buy signals for these tags
        if tag in ("DEAD_WEIGHT", "LEVERAGED"):
            continue

        tech = get_bullish_score(ticker)
        if not tech.get("available"):
            continue

        score = tech["score"]
        if score < threshold:
            continue

        label, emoji = BUY_LABELS.get(min(score, 4), (None, None))
        if not label:
            continue

        alert_key = f"{ticker}_{today}_buy_{label}"
        if alert_key in fired_state:
            continue

        # Build factor summary
        factors = []
        if tech.get("price_bullish"):
            factors.append(f"破MA20(${tech['ma20']:.0f})上 破MA200(${tech['ma200']:.0f})上")
        if tech.get("macd_bullish"):
            factors.append(f"MACD {tech['macd']:+.2f} 金叉")
        if tech.get("obv_bullish"):
            factors.append("OBV上升 (吸籌中)")
        if tech.get("rsi_bullish"):
            factors.append(f"RSI {tech['rsi']:.0f} 健康區間")
        factor_str = " | ".join(factors) or "bullish"

        price = holdings_prices.get(ticker, {}).get("price", tech.get("price", 0))

        # Action language depends on tag + score
        if tag == "SATELLITE" and score >= 2:
            action = (
                f"📋 *Scale to CORE (target >8% weight)*\n"
                f"Current: {weight*100:.1f}% → "
                f"Target: ~12%\n"
                f"Confirm: Daily close above MA20 "
                f"(${tech['ma20']:.2f})"
            )
        elif tag == "CORE" and score >= 3:
            action = (
                f"📋 *Add to winner on strength*\n"
                f"Current: {weight*100:.1f}% → "
                f"consider +2-3% weight\n"
                f"Confirm: Volume above 20-day average"
            )
        elif tag == "PROBLEM" and score >= 3:
            action = (
                f"📋 *Recovery signal — re-evaluate thesis*\n"
                f"Retag to SATELLITE if thesis restated\n"
                f"Do NOT add until thesis documented"
            )
        else:
            action = f"📋 *Monitor — {score}/4 factors bullish*"

        message = (
            f"{emoji} *{ticker} {label}*\n\n"
            f"📊 Tag: {tag} | Weight: {weight*100:.1f}%\n"
            f"💰 Price: ${price:.2f} "
            f"({tech['pct_from_ma20']:+.1f}% vs MA20)\n"
            f"📈 Signals ({score}/4): {factor_str}\n\n"
            f"{action}"
        )

        signals.append({
            "ticker": ticker,
            "tag": tag,
            "score": score,
            "label": label,
            "priority": emoji,
            "message": message,
            "fire_key": alert_key,
        })
        fired_state[alert_key] = {
            "fired_at": datetime.now().isoformat(),
            "score": score,
            "price": price,
        }

    _save_fired(fired_state)
    return sorted(signals, key=lambda x: x["score"], reverse=True)
