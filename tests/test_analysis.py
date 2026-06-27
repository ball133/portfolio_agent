"""Tests for portfolio analysis and AI trend stocks."""
from tools.performance import get_portfolio_analysis, get_portfolio_holdings
from tools.ai_trends import get_ai_trend_stocks


def test_portfolio_analysis():
    """Test portfolio analysis returns total value and holdings."""
    result = get_portfolio_analysis()
    assert result["success"], "Analysis should succeed"
    assert "total_value" in result, "Should have total_value"
    assert "holdings" in result, "Should have holdings list"
    assert len(result["holdings"]) > 0, "Should have at least one holding"


def test_portfolio_holdings():
    """Test get_portfolio_holdings returns dict of holdings."""
    result = get_portfolio_holdings()
    assert result["success"], "Holdings fetch should succeed"
    assert isinstance(result["holdings"], dict), "Should return dict of holdings"


def test_ai_trend_stocks():
    """Test AI trend stocks list is returned correctly."""
    result = get_ai_trend_stocks()
    assert result["success"], "AI trend stocks should be fetched"
    assert "ai_trend_stocks" in result, "Should have ai_trend_stocks key"
    ai_stocks = result["ai_trend_stocks"]
    assert len(ai_stocks) >= 3, "Should have at least 3 AI stocks"
    for stock in ai_stocks:
        assert "ticker" in stock, "Should have ticker"
        assert "company" in stock, "Should have company name"
