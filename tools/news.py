
"""News fetching with Yahoo RSS primary and live fallbacks."""
import feedparser
import yfinance as yf

YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
COMPANY_NAMES = {
    "AAPL": ["Apple", "AAPL", "iPhone", "Mac", "iOS"],
    "NVDA": ["Nvidia", "NVDA", "GeForce", "Jensen Huang", "Blackwell", "CUDA"],
    "TSM": ["TSMC", "TSM", "Taiwan Semiconductor", "Morris Chang"],
    "MSFT": ["Microsoft", "MSFT", "Azure", "Windows", "Copilot", "Satya"],
    "IBM": ["IBM", "International Business Machines", "Big Blue"],
    "GOOGL": ["Google", "GOOGL", "Alphabet", "Sundar Pichai", "Google Cloud"],
    "AVGO": ["Broadcom", "AVGO", "Hock Tan"],
    "09988.HK": ["Alibaba", "BABA", "阿里巴巴", "Jack Ma", "Daniel Zhang"],
    "00700.HK": ["Tencent", "00700", "腾讯", "Pony Ma", "WeChat"],
}
SECTOR_KEYWORDS = [
    "AI chip",
    "semiconductor",
    "GPU",
    "data center",
    "artificial intelligence",
    "machine learning",
    "LLM",
]


def is_relevant(article_title: str, ticker: str) -> bool:
    title_upper = article_title.upper()
    terms = COMPANY_NAMES.get(ticker.upper(), [ticker])
    if any(term.upper() in title_upper for term in terms):
        return True
    if any(keyword.upper() in title_upper for keyword in SECTOR_KEYWORDS):
        return True
    return False


def _classify_relevance(article_title: str, ticker: str):
    title_upper = article_title.upper()
    terms = COMPANY_NAMES.get(ticker.upper(), [ticker])
    if any(term.upper() in title_upper for term in terms):
        return 1
    if any(keyword.upper() in title_upper for keyword in SECTOR_KEYWORDS):
        return 3
    return None


def _split_relevant_articles(raw_articles, ticker, tier_name):
    company_articles = []
    sector_articles = []
    for article in raw_articles:
        title = article.get("title", "")
        if not title or not is_relevant(title, ticker):
            continue
        relevance_tier = _classify_relevance(title, ticker)
        if relevance_tier is None:
            continue
        filtered_article = article.copy()
        filtered_article["relevance_tier"] = relevance_tier
        if relevance_tier == 1:
            company_articles.append(filtered_article)
        else:
            sector_articles.append(filtered_article)
    total_relevant = len(company_articles) + len(sector_articles)
    print(f"[INFO] {ticker} {tier_name}: {len(raw_articles)} fetched, {total_relevant} relevant")
    return company_articles, sector_articles


def _merge_articles(existing_articles, new_articles, num_articles):
    seen = {article.get("title", "") for article in existing_articles}
    for article in new_articles:
        title = article.get("title", "")
        if title in seen:
            continue
        existing_articles.append(article)
        seen.add(title)
        if len(existing_articles) >= num_articles:
            break
    return existing_articles


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _normalize_yfinance_news_item(item, relevance_tier):
    if not isinstance(item, dict):
        return None
    content = _safe_dict(item.get("content", {}))
    clickthrough = _safe_dict(content.get("clickThroughUrl", {}))
    canonical = _safe_dict(content.get("canonicalUrl", {}))
    title = (
        item.get("title", "")
        or content.get("title", "")
        or content.get("summary", "")
        or content.get("description", "")
    )
    url = (
        item.get("link", "")
        or clickthrough.get("url", "")
        or canonical.get("url", "")
    )
    published = (
        item.get("providerPublishTime", "")
        or content.get("pubDate", "")
        or item.get("pubDate", "")
    )
    if not title:
        return None
    return {
        "title": title,
        "url": url,
        "published": published,
        "relevance_tier": relevance_tier,
        "source": "yfinance",
    }


def _get_yfinance_news(ticker):
    raw_articles = []
    t = yf.Ticker(ticker)
    yf_news = t.news or []

    for item in yf_news:
        article = _normalize_yfinance_news_item(item, 2)
        if not article:
            continue
        raw_articles.append(article)
    return raw_articles


def get_stock_news(ticker: str, num_articles: int = 3) -> dict:
    ticker_upper = ticker.upper()
    articles = []
    sector_candidates = []
    try:
        feed = feedparser.parse(YAHOO_RSS.format(ticker=ticker_upper))
        if getattr(feed, "bozo", 0):
            raise feed.bozo_exception
        raw_articles = []
        for entry in feed.entries:
            raw_articles.append({
                "title": entry.title,
                "url": entry.link,
                "published": entry.get("published", ""),
                "relevance_tier": 1,
                "source": "Yahoo RSS"
            })
        company_articles, tier1_sector_articles = _split_relevant_articles(
            raw_articles, ticker_upper, "Tier 1"
        )
        articles = _merge_articles(
            articles,
            company_articles,
            num_articles,
        )
        sector_candidates.extend(tier1_sector_articles)
    except Exception as e:
        print(f"[WARN] Yahoo RSS failed for {ticker_upper}: {e}")
        print(f"[INFO] {ticker_upper} Tier 1: 0 fetched, 0 relevant")

    if len(articles) < num_articles:
        try:
            raw_articles = _get_yfinance_news(ticker_upper)
            company_articles, tier2_sector_articles = _split_relevant_articles(
                raw_articles, ticker_upper, "Tier 2"
            )
            articles = _merge_articles(
                articles,
                company_articles,
                num_articles,
            )
            sector_candidates.extend(tier2_sector_articles)
        except Exception as e:
            print(f"[WARN] yfinance news failed for {ticker_upper}: {e}")
            print(f"[INFO] {ticker_upper} Tier 2: 0 fetched, 0 relevant")

    if not articles:
        try:
            tier3_articles = [
                article.copy() for article in sector_candidates
            ]
            _, tier3_sector_articles = _split_relevant_articles(
                tier3_articles, ticker_upper, "Tier 3"
            )
            articles = _merge_articles(
                articles,
                tier3_sector_articles,
                num_articles,
            )
        except Exception as e:
            print(f"[WARN] Sector keyword news failed for {ticker_upper}: {e}")
            print(f"[INFO] {ticker_upper} Tier 3: 0 fetched, 0 relevant")

    if not articles:
        print(f"[WARN] No news found for {ticker_upper} after 3-tier fallback")

    # Preserve the existing dict contract used by the pipeline and tests.
    return {
        "ticker": ticker_upper,
        "articles": articles[:num_articles],
        "success": len(articles) > 0,
        "has_valid_headlines": len([a for a in articles if a.get("title")]) > 0,
        "is_mock": False,
    }
