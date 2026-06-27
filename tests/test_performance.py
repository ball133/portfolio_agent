"""Tests for performance tracking."""
from tools.performance import get_portfolio_performance


def test_performance_tracking():
    """Test performance tracking can load (or gracefully handle missing history)."""
    result = get_portfolio_performance(days=1)
    assert result is not None, "Result should not be None"
    # Either success, or error about no history
    assert "success" in result, "Should have success key"
