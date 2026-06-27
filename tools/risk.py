"""Risk metrics computation and snapshot price auditing functions."""
from tools.prices import get_stock_price

AI_STACK_LAYERS = {
    "AI_COMPUTE":   {"NVDA", "TSM", "AVGO", "AMD", "MRVL", "MU"},
    "AI_CLOUD":     {"MSFT", "GOOGL", "ORCL", "META", "AMZN"},
    "LEGACY_TECH":  {"IBM", "INTC"},
    "HK_CONSUMER":  {"9988", "0700", "9988.HK", "0700.HK",
                     "09988.HK", "00700.HK"},
    "LEVERAGED":    {"7226", "7226.HK", "LEVERAGED_ETF_HK"},
}


def classify_ai_stack(weights: dict) -> dict:
    """
    Returns layer weights and per-ticker tag.
    weights = {ticker: float} where values sum to ~1.0
    """
    layer_weights = {layer: 0.0 for layer in AI_STACK_LAYERS}
    ticker_layers = {}

    for ticker, w in weights.items():
        matched = False
        for layer, members in AI_STACK_LAYERS.items():
            if ticker.upper() in {m.upper() for m in members}:
                layer_weights[layer] += w
                ticker_layers[ticker] = layer
                matched = True
                break
        if not matched:
            layer_weights.setdefault("UNCLASSIFIED", 0.0)
            layer_weights["UNCLASSIFIED"] += w
            ticker_layers[ticker] = "UNCLASSIFIED"

    return {
        "layer_weights": layer_weights,
        "ticker_layers": ticker_layers,
    }


def tag_positions(holdings: list, weights: dict,
                  ticker_layers: dict) -> list:
    """
    Returns list of dicts with CORE/SATELLITE/PROBLEM/DEAD_WEIGHT tag.
    holdings = list of {ticker, price, value, pct_change, ...}
    """
    tags = []
    for h in holdings:
        ticker  = h.get("ticker", "").upper()
        weight  = weights.get(ticker, weights.get(h.get("ticker", ""), 0))
        layer   = ticker_layers.get(ticker, "UNCLASSIFIED")
        momentum = h.get("pct_change", 0) or 0

        if weight > 0.08 and layer in ("AI_COMPUTE", "AI_CLOUD"):
            tag = "CORE"
        elif layer == "LEGACY_TECH":
            tag = "DEAD_WEIGHT"
        elif weight < 0.06 or layer in ("UNCLASSIFIED", "HK_CONSUMER", "LEVERAGED"):
            tag = "SATELLITE"
        else:
            tag = "SATELLITE"

        if momentum < -0.05 and tag != "CORE":
            tag = "PROBLEM"

        tags.append({
            "ticker":   ticker,
            "tag":      tag,
            "layer":    layer,
            "weight":   weight,
            "momentum": momentum,
        })
    return tags


def compute_risk_metrics(weights):
    """Compute risk metrics from portfolio weights dictionary."""
    sorted_weights = sorted(weights.values(), reverse=True)
    max_weight = sorted_weights[0] if sorted_weights else 0
    top_2_weight = sum(sorted_weights[:2]) if len(sorted_weights) >= 2 else 0
    hhi = sum(w ** 2 for w in weights.values())

    if hhi < 0.15:
        concentration = "well diversified"
    elif 0.15 <= hhi <= 0.25:
        concentration = "moderately concentrated"
    else:
        concentration = "highly concentrated"

    return {
        "max_single_weight": max_weight,
        "top_2_weight_sum": top_2_weight,
        "hhi": hhi,
        "concentration_class": concentration
    }


def audit_snapshot_prices(snapshot):
    """Audit a historical snapshot's prices against current market prices."""
    audit_results = []
    has_stale_prices = False
    portfolio = snapshot.get("portfolio", {})
    holdings_detail = snapshot.get("holdings", [])

    # Create a map of ticker to snapshot price
    snapshot_price_map = {}
    for holding in holdings_detail:
        snapshot_price_map[holding["ticker"]] = holding["price"]

    # Fetch current prices and compare
    for ticker in portfolio.keys():
        current_price_data = get_stock_price(ticker)
        if current_price_data.get("success"):
            snapshot_price = snapshot_price_map.get(ticker, 0)
            current_price = current_price_data["price"]

            if snapshot_price > 0:
                price_diff_pct = ((current_price - snapshot_price) / snapshot_price) * 100
            else:
                price_diff_pct = 0

            if abs(price_diff_pct) > 5:
                has_stale_prices = True

            audit_results.append({
                "ticker": ticker,
                "snapshot_price": snapshot_price,
                "current_price": current_price,
                "diff_pct": round(price_diff_pct, 2),
                "is_stale": abs(price_diff_pct) > 5
            })

    return {
        "audit_results": audit_results,
        "has_stale_prices": has_stale_prices
    }
