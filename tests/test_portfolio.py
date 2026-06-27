"""Tests for portfolio functions (load, add, update, history)."""
from tools.portfolio import (
    load_portfolio,
    add_stock_to_portfolio,
    load_portfolio_history,
    save_portfolio_history
)


def test_portfolio_load():
    """Test portfolio loading works."""
    portfolio = load_portfolio()
    assert isinstance(portfolio, dict), "Portfolio should be a dict"
    assert len(portfolio) > 0, "Should have default holdings"


def test_portfolio_update_dry():
    """Dry test adding/removing a stock without snapshots."""
    # Test adding SPY with save_snapshot=False
    add_result = add_stock_to_portfolio("SPY", 1, save_snapshot=False)
    assert add_result["success"], "Adding SPY should succeed"

    # Check SPY was added
    portfolio = load_portfolio()
    assert "SPY" in portfolio, "SPY should be in portfolio"

    # Remove SPY
    remove_result = add_stock_to_portfolio("SPY", 0, save_snapshot=False)
    assert remove_result["success"], "Removing SPY should succeed"

    # Check SPY is gone
    portfolio = load_portfolio()
    assert "SPY" not in portfolio, "SPY should not be in portfolio anymore"
