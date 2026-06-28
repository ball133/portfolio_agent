"""Facts pass: collect and assemble facts-only JSON summary."""
from datetime import datetime, timedelta
from tools.portfolio import (
    load_portfolio_groups, load_portfolio_history, load_portfolio_state,
    get_all_positions
)
from tools.prices import get_stock_price, check_price_freshness, get_technical_signals
from tools.performance import get_portfolio_performance
from tools.ai_trends import get_ai_trend_stocks
from tools.news import get_stock_news
from tools.risk import audit_snapshot_prices, compute_risk_metrics, classify_ai_stack
from tools.thesis import evaluate_all_thesis
from tools.alerts import get_technical_score

COMPANY_KEYWORDS = {
    "NVDA": ["NVIDIA"],
    "MSFT": ["MICROSOFT"],
    "TSM": ["TSM", "TSMC", "TAIWAN SEMICONDUCTOR"],
    "IBM": ["IBM", "INTERNATIONAL BUSINESS MACHINES", "BIG BLUE"],
    "GOOGL": ["GOOGLE", "ALPHABET", "GOOGL"],
    "AVGO": ["BROADCOM", "AVGO"],
}

def _article_is_relevant(ticker: str, company: str, title: str) -> bool:
    _ = company
    title_upper = title.upper()
    keywords = {ticker.upper()}
    keywords.update(COMPANY_KEYWORDS.get(ticker.upper(), []))
    return any(keyword in title_upper for keyword in keywords if keyword)


def _build_rebalance_recommendations(holdings, weights, risk_metrics):
    if risk_metrics["hhi"] <= 0.30 and risk_metrics["max_single_weight"] <= 0.35:
        return []

    recommendations = []
    sorted_holdings = sorted(
        holdings,
        key=lambda holding: weights.get(holding["ticker"], 0),
        reverse=True,
    )
    if sorted_holdings:
        largest = sorted_holdings[0]
        largest_weight = round(weights.get(largest["ticker"], 0) * 100, 2)
        recommendations.append(
            f"Trim {largest['ticker']} from {largest_weight}% toward the 30-35% range to reduce single-name concentration."
        )
    recommendations.append(
        "Add a non-correlated holding such as a broad-market ETF, healthcare name, or short-duration bond ETF to dilute concentration."
    )
    return recommendations


def run_facts_pass() -> dict:
    """Pass 1: Collect and assemble facts-only JSON summary."""
    snapshot_ts = datetime.now().isoformat(timespec="seconds")
    data_quality_flags = []
    holdings = []
    hk_holdings = []
    all_prices = {}
    portfolio_state = load_portfolio_state()
    portfolio_groups = load_portfolio_groups()
    us_portfolio = portfolio_groups["US"]
    hk_portfolio = portfolio_groups["HK"]

    # Step 1: Load portfolio
    if not us_portfolio and not hk_portfolio:
        data_quality_flags.append("portfolio_empty")
        return {"snapshot_ts": snapshot_ts, "holdings": [], "portfolio": {}, "data_quality_flags": data_quality_flags}

    total_value = 0.0
    hk_total_value_hkd = 0.0
    sector_totals = {}
    weights = {}

    # Sort by shares/value descending for top holdings
    for ticker, shares in us_portfolio.items():
        price_data = get_stock_price(ticker)
        all_prices[ticker] = price_data
        if not price_data.get("success"):
            data_quality_flags.append(f"price_missing_for_{ticker}")
            continue

        value = round(price_data["price"] * shares, 2)
        total_value += value

        holding = {
            "ticker": price_data["ticker"],
            "company": price_data["company_name"],
            "shares": shares,
            "price": price_data["price"],
            "value": value,
            "sector": price_data["sector"],
            "market": price_data.get("market", "US"),
            "currency": price_data.get("currency", "USD"),
            "cost_basis": portfolio_state.get("cost_basis", {}).get(ticker),
        }
        holdings.append(holding)

        sector = price_data.get("sector", "Unknown")
        sector_totals[sector] = sector_totals.get(sector, 0.0) + value

    for ticker, shares in hk_portfolio.items():
        price_data = get_stock_price(ticker)
        all_prices[ticker] = price_data
        if not price_data.get("success"):
            data_quality_flags.append(f"price_missing_for_{ticker}")
            continue

        value = round(price_data["price"] * shares, 2)
        hk_total_value_hkd += value
        hk_holdings.append({
            "ticker": price_data["ticker"],
            "company": price_data["company_name"],
            "shares": shares,
            "price": price_data["price"],
            "value": value,
            "sector": price_data["sector"],
            "market": price_data.get("market", "HK"),
            "currency": price_data.get("currency", "HKD"),
            "cost_basis": portfolio_state.get("cost_basis", {}).get(ticker),
        })

    # Check price freshness
    price_freshness = check_price_freshness(all_prices)
    total_value = round(sum(holding["value"] for holding in holdings), 2)

    # Calculate weights
    if total_value > 0:
        for holding in holdings:
            weights[holding["ticker"]] = holding["value"] / total_value

    # Sector weights
    sector_weights = {}
    if total_value > 0:
        for sector, val in sector_totals.items():
            sector_weights[sector] = val / total_value

    risk_metrics = compute_risk_metrics(weights)
    rebalance_recommendations = _build_rebalance_recommendations(
        holdings, weights, risk_metrics
    )
    rebalance_note = " ".join(rebalance_recommendations)

    # Performance data
    performance = None
    audit_start = None
    perf_data = get_portfolio_performance(days=1)
    if perf_data.get("success") and "performance" in perf_data:
        performance = perf_data["performance"]
        if performance.get("period_days") <= 7:
            data_quality_flags.append("short_performance_window")

        # Audit the start snapshot prices
        history = load_portfolio_history()
        recent_history = [s for s in history if datetime.fromisoformat(s["timestamp"]) >= (datetime.now() - timedelta(days=1))]
        if recent_history:
            first_snapshot = recent_history[0]
            audit_result = audit_snapshot_prices(first_snapshot)
            audit_start = audit_result["audit_results"]
            if audit_result["has_stale_prices"]:
                data_quality_flags.append("start_snapshot_stale_prices")

    # AI trend stocks
    ai_trend_stocks = get_ai_trend_stocks()
    ai_trend_list = []
    if ai_trend_stocks.get("success"):
        for stock in ai_trend_stocks.get("ai_trend_stocks", []):
            ai_trend_list.append({"ticker": stock["ticker"], "company": stock["company"]})

    # News for top 3 holdings
    news = []
    top_holdings = sorted(holdings, key=lambda x: -x["value"])[:3]
    for holding in top_holdings:
        news_data = get_stock_news(holding["ticker"], num_articles=2)
        if news_data.get("success") and news_data.get("articles"):
            for article in news_data["articles"]:
                headline = article.get("title", "")
                if not _article_is_relevant(
                    holding["ticker"], holding["company"], headline
                ):
                    continue
                news.append({
                    "ticker": holding["ticker"],
                    "headline": headline,
                    "source": article.get("source", article.get("publisher", "")),
                    "published_at": article.get("published", article.get("timestamp", "")),
                    "url": article.get("url", article.get("link", ""))
                })
            if not any(item["ticker"] == holding["ticker"] for item in news):
                data_quality_flags.append(f"news_missing_for_{holding['ticker']}")
        else:
            data_quality_flags.append(f"news_missing_for_{holding['ticker']}")

    # Get stack for facts (still need for ai_stack in output)
    stack = classify_ai_stack(holdings, hk_holdings)

    # Use get_all_positions() for position tags from new portfolio system
    position_tags = get_all_positions()

    technicals = {
        pos["ticker"]: get_technical_score(pos["ticker"])
        for pos in position_tags
    }
    news_map = {}
    for n in news:
        ticker = n["ticker"]
        if ticker not in news_map:
            news_map[ticker] = []
        news_map[ticker].append(n["headline"])
    position_tags = evaluate_all_thesis(
        position_tags,
        technicals,
        news_map,
        critic_narrative=""
    )

    # Final facts JSON
    facts = {
        "snapshot_ts": snapshot_ts,
        "holdings": holdings,
        "portfolio": {
            "total_value": total_value,
            "weights": weights,
            "sector_weights": sector_weights,
            "hk_total_value_hkd": round(hk_total_value_hkd, 2),
            "notes": portfolio_state.get("notes", ""),
        },
        "hk_holdings": hk_holdings,
        "performance": performance,
        "ai_trend_stocks": ai_trend_list,
        "news": news,
        "start_snapshot_audit": audit_start,
        "price_freshness": price_freshness,
        "data_quality_flags": data_quality_flags,
        "risk_metrics": risk_metrics,
        "rebalance_recommendations": rebalance_recommendations,
        "rebalance_note": rebalance_note,
        "ai_stack": stack["us_layer_weights"],
        "position_tags": position_tags,
    }

    return facts
