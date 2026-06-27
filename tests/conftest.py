
"""Shared pytest fixtures for portfolio agent tests."""
import sys
import os
import json
from datetime import datetime
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import PORTFOLIO_FILE, HISTORY_FILE, LOOP_STATE_FILE
from tools.prices import get_stock_price
from tools.news import get_stock_news


@pytest.fixture(scope="session", autouse=True)
def backup_and_restore_files():
    """Backup portfolio files before tests, restore after."""
    backups = []
    for f in [PORTFOLIO_FILE, HISTORY_FILE]:
        if os.path.exists(f):
            backup_name = f"{f}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(f, backup_name)
            backups.append((f, backup_name))
    yield
    for original, backup in backups:
        if os.path.exists(backup):
            if os.path.exists(original):
                os.remove(original)
            os.rename(backup, original)


@pytest.fixture(scope="function", autouse=True)
def cleanup_loop_state_file():
    """Cleanup loop_state.json before and after each test."""
    if os.path.exists(LOOP_STATE_FILE):
        os.remove(LOOP_STATE_FILE)
    yield
    if os.path.exists(LOOP_STATE_FILE):
        os.remove(LOOP_STATE_FILE)


@pytest.fixture(scope="session", autouse=True)
def warn_if_mock_data():
    yield
    tickers = ["AAPL", "NVDA", "MSFT", "TSM"]
    price_results = {ticker: get_stock_price(ticker) for ticker in tickers}
    mock_status = {ticker: result.get("is_mock", False) for ticker, result in price_results.items()}
    print(f"\n[DATA] is_mock by ticker: {mock_status}")
    mock_tickers = [ticker for ticker, is_mock in mock_status.items() if is_mock]
    if mock_tickers:
        print(f"\n[TEST WARNING] Mock prices: {mock_tickers}")
        print("[TEST WARNING] Not suitable for real trading decisions.")
    else:
        print(f"\n[DATA] All prices are live ✓")
