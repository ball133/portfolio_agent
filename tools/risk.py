"""Risk metrics computation and snapshot price auditing functions."""
from tools.prices import get_stock_price


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
