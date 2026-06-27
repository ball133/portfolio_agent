
"""Stock price fetching and freshness checking functions."""
import os
import yfinance as yf
from datetime import datetime
from config.settings import STATE_DIR

YFINANCE_CACHE_DIR = os.path.join(STATE_DIR, "yfinance_cache")
os.makedirs(YFINANCE_CACHE_DIR, exist_ok=True)
yf.set_tz_cache_location(YFINANCE_CACHE_DIR)

# Mock stock prices for testing/backup
MOCK_PRICES = {
    "AAPL": {"price": 220.50, "currency": "USD", "company_name": "Apple Inc.", "sector": "Technology"},
    "NVDA": {"price": 1520.75, "currency": "USD", "company_name": "NVIDIA Corporation", "sector": "Technology"},
    "TSM": {"price": 185.30, "currency": "USD", "company_name": "Taiwan Semiconductor Manufacturing", "sector": "Technology"},
    "MSFT": {"price": 480.25, "currency": "USD", "company_name": "Microsoft Corporation", "sector": "Technology"},
    "NOW": {"price": 750.00, "currency": "USD", "company_name": "ServiceNow, Inc.", "sector": "Technology"},
    "XYZ": {"price": 100.00, "currency": "USD", "company_name": "XYZ Corp", "sector": "Unknown"},
}


def normalize_ticker(ticker: str) -> str:
    """Remove any $ prefix, ensure HK tickers have correct zero-padding for yfinance."""
    ticker = ticker.replace("$", "").strip().upper()
    # yfinance HK format: 4-digit code + .HK
    if ticker.endswith(".HK"):
        code = ticker.replace(".HK", "")
        ticker = f"{int(code):04d}.HK"
    return ticker


def is_hk_ticker(ticker: str) -> bool:
    return ticker.upper().endswith(".HK")


def _yfinance_ticker_candidates(ticker: str):
    normalized = normalize_ticker(ticker)
    if not is_hk_ticker(normalized):
        return [normalized]

    root = normalized[:-3]
    candidate_roots = [root]
    if root.startswith("0") and len(root) > 1:
        candidate_roots.append(root[1:])
    normalized_root = root.lstrip("0") or root
    candidate_roots.append(normalized_root)

    candidates = []
    for candidate_root in candidate_roots:
        candidate = f"{candidate_root}.HK"
        if candidate not in candidates:
            candidates.append(candidate)
    return candidates


def _get_mock_price(ticker):
    """Get mock price for ticker."""
    ticker_upper = ticker.upper()
    market = "HK" if is_hk_ticker(ticker_upper) else "US"
    currency = "HKD" if market == "HK" else "USD"
    print(f"[WARN] yfinance failed for {ticker}: Using mock price")
    if ticker_upper in MOCK_PRICES:
        mock = MOCK_PRICES[ticker_upper]
        return {
            "ticker": ticker_upper,
            "price": round(mock["price"], 2),
            "currency": currency if market == "HK" else mock["currency"],
            "company_name": mock["company_name"],
            "sector": mock["sector"],
            "fetched_at": datetime.now().isoformat(),
            "is_mock": True,
            "success": True,
            "market": market,
        }
    return {
        "ticker": ticker_upper,
        "error": "Could not retrieve price",
        "success": False,
        "is_mock": False,
        "fetched_at": datetime.now().isoformat(),
        "currency": currency,
        "market": market,
    }


def get_stock_price(ticker: str) -> dict:
    ticker_upper = ticker.upper()
    market = "HK" if is_hk_ticker(ticker_upper) else "US"
    last_error = None
    for candidate in _yfinance_ticker_candidates(ticker_upper):
        try:
            t = yf.Ticker(candidate)
            fast_info = t.fast_info
            price = (
                fast_info.get("last_price")
                or fast_info.get("lastPrice")
            )
            if price is None:
                info = t.info or {}
                price = info.get("currentPrice") or info.get("regularMarketPreviousClose")
            else:
                info = t.info or {}

            if price is None:
                hist = t.history(period="1d")
                if not hist.empty:
                    price = hist["Close"].iloc[-1]
            if price is None:
                raise ValueError("price missing from yfinance fast_info/info/history")

            name = info.get("longName", ticker_upper)
            return {
                "ticker": ticker_upper,
                "price": round(price, 2),
                "company": name,
                "company_name": name,
                "is_mock": False,
                "fetched_at": datetime.now().isoformat(),
                "success": True,
                "currency": "HKD" if market == "HK" else info.get("currency", "USD"),
                "sector": info.get("sector", "Unknown"),
                "market": market,
            }
        except Exception as e:
            last_error = e

    print(f"[WARN] yfinance failed for {ticker_upper}: {last_error}")
    return _get_mock_price(ticker_upper)


def get_portfolio_price_map():
    """Fetch the latest prices for both US and HK holdings in portfolio.json."""
    from tools.portfolio import load_portfolio_groups

    price_map = {}
    for holdings in load_portfolio_groups().values():
        for ticker in holdings:
            price_map[ticker] = get_stock_price(ticker)
    return price_map


def check_price_freshness(prices_dict):
    """Check price freshness (less than 15 min = fresh)."""
    result = {}
    now = datetime.now()
    for ticker, data in prices_dict.items():
        if not data.get("fetched_at"):
            age_minutes = 999
            is_fresh = False
        else:
            try:
                fetched_dt = datetime.fromisoformat(data["fetched_at"])
                age_seconds = (now - fetched_dt).total_seconds()
                age_minutes = age_seconds / 60
                is_fresh = age_minutes < 15
            except Exception:
                age_minutes = 999
                is_fresh = False

        result[ticker] = {
            "price": data.get("price"),
            "fetched_at": data.get("fetched_at"),
            "age_minutes": round(age_minutes, 1),
            "is_fresh": is_fresh,
            "is_mock": data.get("is_mock", False)
        }
    return result
