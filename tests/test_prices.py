"""Tests for stock price fetching and freshness check."""
from tools.prices import get_stock_price, check_price_freshness


def test_stock_price_fetch():
    """Test price fetching for multiple tickers."""
    tickers = ["AAPL", "NVDA", "MSFT", "TSM"]
    for ticker in tickers:
        result = get_stock_price(ticker)
        assert result["success"], f"Should get price for {ticker}"
        assert "price" in result, f"Should have price for {ticker}"
        assert "fetched_at" in result, f"Should have fetched_at for {ticker}"
        assert result["fetched_at"] != "", f"fetched_at should not be empty"


def test_price_freshness_function():
    """Test check_price_freshness function returns correct structure."""
    tickers = ["AAPL", "NVDA"]
    prices = {t: get_stock_price(t) for t in tickers}
    freshness = check_price_freshness(prices)

    assert len(freshness) == 2, "Should have entry for both tickers"
    for ticker in tickers:
        assert ticker in freshness, f"Should have freshness for {ticker}"
        assert "is_fresh" in freshness[ticker], f"Should have is_fresh for {ticker}"
        assert "age_minutes" in freshness[ticker], f"Should have age_minutes for {ticker}"
