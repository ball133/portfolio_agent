
import os
import json
import pytest
os.environ["THESIS_STATE_FILE"] = "state/thesis_state_test.json"

from tools.thesis import evaluate_thesis

INTACT_TECH = {
    "score": 1, "rsi": 58,
    "price_bearish": False, "macd_bearish": False,
    "obv_bearish": False, "rsi_bearish": False,
    "price_bullish": True,
}
BEARISH_TECH = {
    "score": 3, "rsi": 38,
    "price_bearish": True, "macd_bearish": True,
    "obv_bearish": True, "rsi_bearish": True,
    "price_bullish": False,
}


def teardown_function():
    if os.path.exists("state/thesis_state_test.json"):
        os.remove("state/thesis_state_test.json")


def test_dead_weight_always_broken():
    s = evaluate_thesis("IBM", "DEAD_WEIGHT",
                        INTACT_TECH, [])
    assert s == "Broken"


def test_leveraged_always_broken():
    s = evaluate_thesis("7226.HK", "LEVERAGED",
                        INTACT_TECH, [])
    assert s == "Broken"


def test_core_intact_with_good_tech():
    s = evaluate_thesis("NVDA", "CORE",
                        INTACT_TECH, [])
    assert s == "Intact"


def test_core_watch_on_bearish_tech():
    s = evaluate_thesis("GOOGL", "CORE",
                        BEARISH_TECH, [])
    assert s == "Watch"


def test_watch_streak_to_broken():
    # Simulate 3 consecutive Watch sessions
    for _ in range(3):
        evaluate_thesis("MSFT", "SATELLITE",
                        BEARISH_TECH, [])
    s = evaluate_thesis("MSFT", "SATELLITE",
                        BEARISH_TECH, [])
    assert s == "Broken"


def test_broken_keywords_in_critic():
    narrative = ("guidance cut and margin pressure "
                 "signal structural decline ahead")
    s = evaluate_thesis("AVGO", "SATELLITE",
                        INTACT_TECH, [], narrative)
    assert s == "Broken"


def test_intact_keywords_in_critic():
    narrative = ("strong demand and AI demand drove "
                 "record revenue with market share gain")
    s = evaluate_thesis("TSM", "CORE",
                        INTACT_TECH, [], narrative)
    assert s == "Intact"
