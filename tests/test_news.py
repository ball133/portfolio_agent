"""Tests for news fetching and quality."""
from tools.news import get_stock_news


def test_news_fetching():
    """Test news fetch returns articles with relevance tiers."""
    result = get_stock_news("NVDA", num_articles=3)
    assert result["success"], "News fetch should succeed"
    articles = result["articles"]
    assert len(articles) >= 1, "Should find at least 1 article"
    for article in articles:
        assert "relevance_tier" in article, "Should have relevance_tier"


def test_news_quality():
    """Test news articles have non-empty relevant headlines."""
    news_data = get_stock_news("NVDA", 3)
    assert isinstance(news_data, dict), "Result should be dict"
    assert news_data["success"], "News fetch success=True"
    articles = news_data["articles"]
    assert len(articles) > 0, "Should have at least one article"

    first_article = articles[0]
    assert "title" in first_article, "Should have 'title' key"
    title = first_article["title"]
    assert len(title.strip()) > 0, "Headline should not be empty"
