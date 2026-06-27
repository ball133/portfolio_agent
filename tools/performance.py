"""Portfolio analysis and performance tracking functions."""
from datetime import datetime, timedelta
from tools.portfolio import load_portfolio, load_portfolio_history, load_portfolio_details
from tools.prices import get_stock_price


def get_portfolio_holdings() -> dict:
    """Fetches the current portfolio holdings."""
    portfolio = load_portfolio()
    return {"holdings": portfolio, "success": True}


def get_portfolio_analysis() -> dict:
    """Get comprehensive analysis of the portfolio including total value and allocation."""
    try:
        portfolio = load_portfolio()
        holding_details = load_portfolio_details()
        if not portfolio:
            return {"error": "Portfolio is empty", "success": False}

        total_value = 0.0
        hk_total_value_hkd = 0.0
        holdings_detail = []
        hk_holdings_detail = []
        sectors = {}

        for ticker, shares in portfolio.items():
            price_data = get_stock_price(ticker)
            if price_data["success"]:
                position_value = round(price_data["price"] * shares, 2)
                market = holding_details.get(ticker, {}).get("market", price_data.get("market", "US"))
                holding_record = {
                    "ticker": ticker,
                    "shares": shares,
                    "price": price_data["price"],
                    "value": position_value,
                    "company_name": price_data["company_name"],
                    "sector": price_data.get("sector", "Unknown"),
                    "currency": price_data["currency"],
                    "market": market,
                    "cost_basis": holding_details.get(ticker, {}).get("cost_basis"),
                }
                if market == "HK":
                    hk_total_value_hkd += position_value
                    hk_holdings_detail.append(holding_record)
                    holdings_detail.append(holding_record)
                    continue

                total_value += position_value
                sector = holding_record["sector"]
                sectors[sector] = sectors.get(sector, 0) + position_value
                holdings_detail.append(holding_record)

        allocation = []
        for holding in holdings_detail:
            if total_value > 0:
                allocation_percent = (holding["value"] / total_value) * 100
                holding["allocation_percent"] = round(allocation_percent, 2)
                allocation.append({
                    "ticker": holding["ticker"],
                    "allocation_percent": round(allocation_percent, 2)
                })

        sector_allocation = []
        for sector, value in sectors.items():
            if total_value > 0:
                sector_percent = (value / total_value) * 100
                sector_allocation.append({
                    "sector": sector,
                    "value": round(value, 2),
                    "allocation_percent": round(sector_percent, 2)
                })

        return {
            "total_value": round(total_value, 2),
            "hk_total_value_hkd": round(hk_total_value_hkd, 2),
            "holdings": holdings_detail,
            "hk_holdings": hk_holdings_detail,
            "allocation": allocation,
            "sector_allocation": sector_allocation,
            "success": True
        }
    except Exception as e:
        return {"error": str(e), "success": False}


def get_portfolio_performance(days: int = 30) -> dict:
    """Get historical performance of the portfolio."""
    try:
        history = load_portfolio_history()
        if not history:
            return {"error": "No portfolio history available yet", "success": False}

        cutoff_date = datetime.now() - timedelta(days=days)
        recent_history = [s for s in history if datetime.fromisoformat(s["timestamp"]) >= cutoff_date]

        if not recent_history:
            return {"error": f"No history available for the last {days} days", "success": False}

        first_snapshot = recent_history[0]
        last_snapshot = recent_history[-1]

        performance = {}
        if first_snapshot.get("total_value") and last_snapshot.get("total_value"):
            # Calculate actual period days from timestamps
            start_dt = datetime.fromisoformat(first_snapshot["timestamp"])
            end_dt = datetime.fromisoformat(last_snapshot["timestamp"])
            actual_period_days = (end_dt - start_dt).total_seconds() / 86400

            absolute_return = last_snapshot["total_value"] - first_snapshot["total_value"]
            percent_return = (absolute_return / first_snapshot["total_value"]) * 100
            performance = {
                "period_days": actual_period_days,
                "start_date": first_snapshot["timestamp"],
                "end_date": last_snapshot["timestamp"],
                "start_value": first_snapshot["total_value"],
                "end_value": last_snapshot["total_value"],
                "absolute_return": round(absolute_return, 2),
                "percent_return": round(percent_return, 2),
                "snapshots_available": len(recent_history)
            }

        return {
            "performance": performance,
            "success": True
        }
    except Exception as e:
        return {"error": str(e), "success": False}
