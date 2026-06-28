from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np


def _make_hist(prices: list) -> pd.DataFrame:
    """Build a minimal yfinance-style history df."""
    closes = pd.Series(prices)
    volumes = pd.Series([1_000_000] * len(prices))
    df = pd.DataFrame({
        "Close": closes,
        "Volume": volumes,
    })
    return df


@patch("tools.alerts.yf.Ticker")
@patch("tools.alerts.get_technical_score")
@patch("tools.alerts._load_fired")
@patch("tools.alerts._save_fired")
def test_rebound_guard_suppresses_sell(mock_save, mock_load, mock_get_tech, mock_ticker):
    """+5.71% last session → sell suppressed."""
    mock_load.return_value = {}
    prices = list(range(300, 370)) + [352, 372]
    mock_ticker.return_value.history.return_value = _make_hist(prices)
    mock_get_tech.return_value = {
        "available": True, "score": 3, "price": 372.97,
        "price_bearish": True, "macd_bearish": True,
        "obv_bearish": True, "rsi_bearish": True,
        "ma20": 360, "ma200": 365, "macd": -2.5, "rsi": 40
    }
    from tools.alerts import get_sell_signals
    tags = [{"ticker": "MSFT", "tag": "SATELLITE",
             "weight": 0.058,
             "thesis_status": "Watch"}]
    sigs = get_sell_signals(tags, {
        "MSFT": {"price": 372.97}})
    suppressed = [s for s in sigs
                  if s["label"] == "SUPPRESSED"]
    assert len(suppressed) == 1
    assert "rebound" in suppressed[0]["message"].lower()


@patch("tools.alerts.yf.Ticker")
@patch("tools.alerts.get_technical_score")
@patch("tools.alerts._load_fired")
@patch("tools.alerts._save_fired")
def test_52w_low_guard_suppresses_sell(mock_save, mock_load, mock_get_tech, mock_ticker):
    """Price within 3% of 52w low → sell suppressed."""
    mock_load.return_value = {}
    prices = list(range(300, 370)) + [305, 306]
    mock_ticker.return_value.history.return_value = _make_hist(prices)
    mock_get_tech.return_value = {
        "available": True, "score": 3, "price": 306,
        "price_bearish": True, "macd_bearish": True,
        "obv_bearish": True, "rsi_bearish": True,
        "ma20": 310, "ma200": 320, "macd": -2.5, "rsi": 40
    }
    from tools.alerts import get_sell_signals
    tags = [{"ticker": "MSFT", "tag": "SATELLITE",
             "weight": 0.058,
             "thesis_status": "Watch"}]
    sigs = get_sell_signals(tags, {
        "MSFT": {"price": 306}})
    suppressed = [s for s in sigs
                  if s["label"] == "SUPPRESSED"]
    assert len(suppressed) == 1
    assert "52w" in suppressed[0]["message"].lower()


@patch("tools.alerts.yf.Ticker")
@patch("tools.alerts.get_technical_score")
@patch("tools.alerts._load_fired")
@patch("tools.alerts._save_fired")
def test_dead_weight_ignores_guards(mock_save, mock_load, mock_get_tech, mock_ticker):
    """DEAD_WEIGHT always fires — guards do not apply."""
    mock_load.return_value = {}
    prices = list(range(250, 270)) + [269, 271]
    mock_ticker.return_value.history.return_value = _make_hist(prices)
    mock_get_tech.return_value = {
        "available": True, "score": 0, "price": 271.63,
        "price_bearish": False, "macd_bearish": False,
        "obv_bearish": False, "rsi_bearish": False,
        "ma20": 270, "ma200": 265, "macd": 0.5, "rsi": 50
    }
    from tools.alerts import get_sell_signals
    tags = [{"ticker": "IBM", "tag": "DEAD_WEIGHT",
             "weight": 0.085,
             "thesis_status": "Broken"}]
    sigs = get_sell_signals(tags, {
        "IBM": {"price": 271.63}})
    fired = [s for s in sigs
             if s["label"] != "SUPPRESSED"]
    assert len(fired) >= 1
