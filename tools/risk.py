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


def classify_ai_stack(us_holdings: list, hk_holdings: list) -> dict:
    """
    Returns layer weights (for US sleeve and global) and per-ticker layer.
    """
    us_total = sum(h["value"] for h in us_holdings)
    hk_total = sum(h["value"] for h in hk_holdings)
    
    us_layer_weights = {layer: 0.0 for layer in AI_STACK_LAYERS}
    global_layer_weights = {layer: 0.0 for layer in AI_STACK_LAYERS}
    ticker_layers = {}
    us_weights = {}
    hk_weights = {}
    global_weights = {}
    
    # Calculate US weights and layers
    for h in us_holdings:
        ticker = h["ticker"].upper()
        w = h["value"] / us_total if us_total > 0 else 0.0
        us_weights[ticker] = w
        
        matched = False
        for layer, members in AI_STACK_LAYERS.items():
            if ticker in {m.upper() for m in members}:
                us_layer_weights[layer] += w
                ticker_layers[ticker] = layer
                matched = True
                break
        if not matched:
            us_layer_weights.setdefault("UNCLASSIFIED", 0.0)
            us_layer_weights["UNCLASSIFIED"] += w
            ticker_layers[ticker] = "UNCLASSIFIED"
            
    # Calculate HK weights and layers
    for h in hk_holdings:
        ticker = h["ticker"].upper()
        w = h["value"] / hk_total if hk_total > 0 else 0.0
        hk_weights[ticker] = w
        
        matched = False
        for layer, members in AI_STACK_LAYERS.items():
            if ticker in {m.upper() for m in members}:
                ticker_layers[ticker] = layer
                matched = True
                break
        if not matched:
            ticker_layers[ticker] = "UNCLASSIFIED"

    return {
        "us_layer_weights": us_layer_weights,
        "ticker_layers": ticker_layers,
        "us_weights": us_weights,
        "hk_weights": hk_weights,
        "us_total": us_total,
        "hk_total": hk_total,
    }


def tag_positions(us_holdings: list, hk_holdings: list,
                  ticker_layers: dict, us_weights: dict, hk_weights: dict) -> list:
    """
    Returns list of dicts with CORE/SATELLITE/PROBLEM/DEAD_WEIGHT/LEVERAGED tag.
    """
    tags = []
    
    # Tag US holdings
    for h in us_holdings:
        ticker = h["ticker"].upper()
        layer = ticker_layers.get(ticker, "UNCLASSIFIED")
        weight = us_weights.get(ticker, 0.0)
        momentum = h.get("pct_change", 0) or 0

        if weight > 0.08 and layer in ("AI_COMPUTE", "AI_CLOUD"):
            tag = "CORE"
        elif layer == "LEGACY_TECH":
            tag = "DEAD_WEIGHT"
        else:
            tag = "SATELLITE"

        if momentum < -0.05 and tag != "CORE":
            tag = "PROBLEM"

        tags.append({
            "ticker": ticker,
            "tag": tag,
            "layer": layer,
            "weight": weight,
            "weight_in_sleeve": "US",
            "momentum": momentum,
            "thesis_status": "Broken" if tag == "DEAD_WEIGHT" else "Watch" if ticker == "MSFT" else "Intact",
        })
        
    # Tag HK holdings
    for h in hk_holdings:
        ticker = h["ticker"].upper()
        layer = ticker_layers.get(ticker, "UNCLASSIFIED")
        weight = hk_weights.get(ticker, 0.0)
        momentum = h.get("pct_change", 0) or 0

        if layer == "LEVERAGED":
            tag = "LEVERAGED"
        elif weight > 0.08 and layer == "HK_CONSUMER":
            tag = "CORE"
        else:
            tag = "SATELLITE"

        if momentum < -0.05 and tag != "CORE":
            tag = "PROBLEM"

        tags.append({
            "ticker": ticker,
            "tag": tag,
            "layer": layer,
            "weight": weight,
            "weight_in_sleeve": "HK",
            "momentum": momentum,
            "thesis_status": "Broken" if tag == "LEVERAGED" else "Intact",
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
