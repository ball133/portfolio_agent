"""Portfolio loading and saving functions."""
import json
import os
from datetime import datetime
from config.settings import PORTFOLIO_FILE, HISTORY_FILE, DEFAULT_PORTFOLIO, ARCHIVE_FILE


def is_hk_ticker(ticker: str) -> bool:
    return ticker.upper().endswith(".HK")


def _default_portfolio_state():
    return {
        "holdings": DEFAULT_PORTFOLIO.copy(),
        "hk_holdings": {},
        "cost_basis": {},
        "notes": "",
    }


def _normalize_portfolio_state(data):
    if not isinstance(data, dict):
        return _default_portfolio_state()

    if "holdings" in data or "hk_holdings" in data:
        state = _default_portfolio_state()
        state["holdings"] = dict(data.get("holdings", {}))
        state["hk_holdings"] = dict(data.get("hk_holdings", {}))
        state["cost_basis"] = dict(data.get("cost_basis", {}))
        state["notes"] = data.get("notes", "")
        return state

    # Backward compatibility: legacy flat ticker->shares file.
    state = _default_portfolio_state()
    for ticker, shares in data.items():
        target = "hk_holdings" if is_hk_ticker(ticker) else "holdings"
        state[target][ticker.upper()] = shares
    return state


def _split_holdings_by_market(portfolio):
    us_holdings = {}
    hk_holdings = {}
    for ticker, shares in portfolio.items():
        if is_hk_ticker(ticker):
            hk_holdings[ticker.upper()] = shares
        else:
            us_holdings[ticker.upper()] = shares
    return us_holdings, hk_holdings


def load_portfolio_state():
    """Load the structured portfolio state from disk."""
    if not os.path.exists(PORTFOLIO_FILE):
        return _default_portfolio_state()

    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as file_obj:
            return _normalize_portfolio_state(json.load(file_obj))
    except Exception:
        return _default_portfolio_state()


def load_portfolio_groups():
    """Load US/HK holdings separately."""
    state = load_portfolio_state()
    return {
        "US": dict(state.get("holdings", {})),
        "HK": dict(state.get("hk_holdings", {})),
    }


def load_portfolio_details():
    """Load holding metadata keyed by ticker."""
    state = load_portfolio_state()
    cost_basis = state.get("cost_basis", {})
    details = {}
    for market, holdings in load_portfolio_groups().items():
        for ticker, shares in holdings.items():
            details[ticker] = {
                "ticker": ticker,
                "shares": shares,
                "market": market,
                "cost_basis": cost_basis.get(ticker),
            }
    return details


def load_portfolio():
    """Load the current portfolio as a combined ticker->shares mapping."""
    groups = load_portfolio_groups()
    combined = {}
    combined.update(groups["US"])
    combined.update(groups["HK"])
    return combined


def save_portfolio(portfolio, save_snapshot=True):
    """Save portfolio to JSON file and record history."""
    try:
        state = load_portfolio_state()
        if isinstance(portfolio, dict) and ("holdings" in portfolio or "hk_holdings" in portfolio):
            state = _normalize_portfolio_state(portfolio)
        else:
            us_holdings, hk_holdings = _split_holdings_by_market(portfolio)
            state["holdings"] = us_holdings
            state["hk_holdings"] = hk_holdings

        with open(PORTFOLIO_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)

        if save_snapshot:
            save_portfolio_history(load_portfolio())

        return {"success": True, "message": "Portfolio saved successfully"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def load_portfolio_history():
    """Load historical portfolio data."""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_portfolio_history(portfolio, save_snapshot=True):
    """Save portfolio snapshot to history with timestamp."""
    from tools.prices import get_stock_price  # Import here to avoid circular dep

    if not save_snapshot:
        return

    history = load_portfolio_history()
    timestamp = datetime.now().isoformat()
    state = load_portfolio_state()
    cost_basis = state.get("cost_basis", {})
    us_holdings, hk_holdings = _split_holdings_by_market(portfolio)

    # Calculate current value for history (USD portfolio tracked separately from HKD holdings).
    total_value = 0.0
    hk_total_value_hkd = 0.0
    holdings_detail = []
    hk_holdings_detail = []
    for ticker, shares in us_holdings.items():
        price_data = get_stock_price(ticker)
        if price_data["success"]:
            position_value = round(price_data["price"] * shares, 2)
            total_value += position_value
            holdings_detail.append({
                "ticker": ticker,
                "shares": shares,
                "price": price_data["price"],
                "value": position_value,
                "market": "US",
                "currency": price_data.get("currency", "USD"),
                "cost_basis": cost_basis.get(ticker),
            })

    for ticker, shares in hk_holdings.items():
        price_data = get_stock_price(ticker)
        if price_data["success"]:
            position_value = round(price_data["price"] * shares, 2)
            hk_total_value_hkd += position_value
            hk_holdings_detail.append({
                "ticker": ticker,
                "shares": shares,
                "price": price_data["price"],
                "value": position_value,
                "market": "HK",
                "currency": price_data.get("currency", "HKD"),
                "cost_basis": cost_basis.get(ticker),
            })

    snapshot = {
        "timestamp": timestamp,
        "portfolio": us_holdings,
        "hk_portfolio": hk_holdings,
        "total_value": round(total_value, 2) if total_value > 0 else None,
        "hk_total_value_hkd": round(hk_total_value_hkd, 2) if hk_total_value_hkd > 0 else None,
        "holdings": holdings_detail,
        "hk_holdings": hk_holdings_detail,
    }

    history.append(snapshot)

    # Keep last 100 snapshots
    if len(history) > 100:
        history = history[-100:]

    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        print(f"[Warning] Could not save history: {e}")


def add_stock_to_portfolio(ticker: str, shares: int, save_snapshot=True):
    """Add or update a stock in the portfolio."""
    try:
        shares = int(shares)
        if shares < 0:
            return {"error": "Shares cannot be negative", "success": False}

        portfolio = load_portfolio_state()
        ticker_upper = ticker.upper()
        market_key = "hk_holdings" if is_hk_ticker(ticker_upper) else "holdings"
        holdings = portfolio[market_key]

        if shares == 0:
            if ticker_upper in holdings:
                del holdings[ticker_upper]
                save_result = save_portfolio(portfolio, save_snapshot=save_snapshot)
                return {"message": f"Removed {ticker_upper} from portfolio", "success": save_result["success"]}
            else:
                return {"message": f"{ticker_upper} not in portfolio", "success": True}

        holdings[ticker_upper] = holdings.get(ticker_upper, 0) + shares
        save_result = save_portfolio(portfolio, save_snapshot=save_snapshot)
        return {"message": f"Updated portfolio: {ticker_upper} now has {holdings[ticker_upper]} shares", "success": save_result["success"]}
    except ValueError:
        return {"error": "Shares must be an integer", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def reset_performance_history(keep_latest=0):
    """Reset performance history, keeping only N latest snapshots and archiving the rest."""
    history = load_portfolio_history()

    if len(history) <= keep_latest:
        print(f"[INFO] Only {len(history)} snapshots exist — no need to reset.")
        return

    # Split into keep and archive
    if keep_latest <= 0:
        keep_history = []
        archive_history = history
    else:
        keep_history = history[-keep_latest:]
        archive_history = history[:-keep_latest]

    # Load existing archive (if any)
    existing_archive = []
    if os.path.exists(ARCHIVE_FILE):
        try:
            with open(ARCHIVE_FILE, "r") as f:
                existing_archive = json.load(f)
        except Exception:
            print(f"[WARN] Couldn't load existing archive — starting fresh.")

    # Append archived snapshots to archive
    existing_archive.extend(archive_history)

    # Write archive and new history
    with open(ARCHIVE_FILE, "w") as f:
        json.dump(existing_archive, f, indent=2)

    with open(HISTORY_FILE, "w") as f:
        json.dump(keep_history, f, indent=2)

    print(f"[SUCCESS] Archived {len(archive_history)} snapshots, kept {len(keep_history)}.")


# ================================================
# NEW: Dynamic portfolio management (data/portfolio.json)
# ================================================
from datetime import date

# Use absolute path based on this file's location
_tools_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_tools_dir)
DYNAMIC_PORTFOLIO_FILE = os.path.join(_project_root, "data", "portfolio.json")
DATA_DIR = os.path.join(_project_root, "data")


def _load_dynamic() -> dict:
    # Debug prints
    print(f"[DEBUG] tools/portfolio.py: __file__ = {__file__}")
    print(f"[DEBUG] tools/portfolio.py: _tools_dir = {_tools_dir}")
    print(f"[DEBUG] tools/portfolio.py: _project_root = {_project_root}")
    print(f"[DEBUG] tools/portfolio.py: DYNAMIC_PORTFOLIO_FILE = {DYNAMIC_PORTFOLIO_FILE}")
    print(f"[DEBUG] tools/portfolio.py: exists? {os.path.exists(DYNAMIC_PORTFOLIO_FILE)}")
    if os.path.exists(_project_root):
        print(f"[DEBUG] tools/portfolio.py: _project_root contents: {os.listdir(_project_root)}")
    if os.path.exists(os.path.join(_project_root, "data")):
        print(f"[DEBUG] tools/portfolio.py: data/ contents: {os.listdir(os.path.join(_project_root, 'data'))}")
    with open(DYNAMIC_PORTFOLIO_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_dynamic(data: dict):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DYNAMIC_PORTFOLIO_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_all_positions() -> list:
    """Return flat list of all positions, all sleeves."""
    data = _load_dynamic()
    result = []
    for sleeve, sleeve_data in data["sleeves"].items():
        for pos in sleeve_data["positions"]:
            result.append({**pos, "sleeve": sleeve, "currency": sleeve_data["currency"]})
    return result


def get_position(ticker: str) -> dict | None:
    """Return single position dict or None."""
    return next((p for p in get_all_positions() if p["ticker"] == ticker), None)


def add_position(
    sleeve: str,
    ticker: str,
    tag: str,
    weight: float,
    thesis_note: str,
    thesis_status: str = "Intact",
    scale_trigger: float = None,
    core_eligible_at: float = None,
) -> dict:
    """
    Add a new position to a sleeve.
    Raises ValueError if ticker already exists.
    """
    data = _load_dynamic()
    positions = data["sleeves"][sleeve]["positions"]
    if any(p["ticker"] == ticker for p in positions):
        raise ValueError(f"{ticker} already exists in {sleeve}")
    new_pos = {
        "ticker": ticker,
        "tag": tag,
        "weight": round(weight, 4),
        "thesis_status": thesis_status,
        "thesis_note": thesis_note,
        "scale_trigger": scale_trigger,
        "core_eligible_at": core_eligible_at,
        "added_date": date.today().isoformat(),
    }
    positions.append(new_pos)
    _save_dynamic(data)
    return new_pos


def remove_position(ticker: str) -> bool:
    """
    Remove position by ticker across all sleeves.
    Returns True if removed, False if not found.
    """
    data = _load_dynamic()
    found = False
    for sleeve_data in data["sleeves"].values():
        before = len(sleeve_data["positions"])
        sleeve_data["positions"] = [p for p in sleeve_data["positions"] if p["ticker"] != ticker]
        if len(sleeve_data["positions"]) < before:
            found = True
    if found:
        _save_dynamic(data)
    return found


def update_position(ticker: str, **kwargs) -> dict | None:
    """
    Update any field on an existing position.
    Example: update_position("MSFT", thesis_status="Intact", weight=0.10)
    Returns updated position or None if not found.
    """
    data = _load_dynamic()
    found = None
    for sleeve_data in data["sleeves"].values():
        for pos in sleeve_data["positions"]:
            if pos["ticker"] == ticker:
                pos.update(kwargs)
                found = pos
    if found:
        _save_dynamic(data)
    return found


def update_weight(ticker: str, new_weight: float) -> dict | None:
    """Convenience wrapper for weight update."""
    return update_position(ticker, weight=round(new_weight, 4))


def retag(ticker: str, new_tag: str, new_thesis_status: str = None) -> dict | None:
    """
    Change position tag. Optionally update thesis.
    Example: retag("MSFT", "CORE", "Intact")
    """
    kwargs = {"tag": new_tag}
    if new_thesis_status:
        kwargs["thesis_status"] = new_thesis_status
    return update_position(ticker, **kwargs)


def get_mandate() -> dict:
    return _load_dynamic()["mandate"]


def list_tickers(sleeve: str = None) -> list:
    """Return list of ticker strings."""
    positions = get_all_positions()
    if sleeve:
        positions = [p for p in positions if p["sleeve"] == sleeve]
    return [p["ticker"] for p in positions]
