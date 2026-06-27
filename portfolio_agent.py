from openai import OpenAI
from dotenv import load_dotenv
import os
import json
import sys
import yfinance as yf
from datetime import datetime, timedelta
import requests


load_dotenv()

YFINANCE_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state", "yfinance_cache")
os.makedirs(YFINANCE_CACHE_DIR, exist_ok=True)
yf.set_tz_cache_location(YFINANCE_CACHE_DIR)


DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
PORTFOLIO_FILE = "portfolio.json"
HISTORY_FILE = "portfolio_history.json"


def load_portfolio():
    """Load portfolio from JSON file, or create default if it doesn't exist."""
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warning] Could not load portfolio: {e}, using default")
    return {
        "AAPL": 10,
        "NVDA": 5,
        "TSM": 3,
        "MSFT": 2
    }


def save_portfolio(portfolio, save_snapshot=True):
    """Save portfolio to JSON file and record history."""
    try:
        with open(PORTFOLIO_FILE, "w") as f:
            json.dump(portfolio, f, indent=2)
        
        # Record history snapshot
        save_portfolio_history(portfolio, save_snapshot=save_snapshot)
        
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


def reset_performance_history(keep_latest=1):
    """Reset performance history, keeping only N latest snapshots and archiving the rest."""
    history = load_portfolio_history()
    
    if len(history) <= keep_latest:
        print(f"[INFO] Only {len(history)} snapshots exist — no need to reset.")
        return
    
    # Split into keep and archive
    keep_history = history[-keep_latest:]
    archive_history = history[:-keep_latest]
    
    # Load existing archive (if any)
    ARCHIVE_FILE = "performance_history_archive.json"
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


def save_portfolio_history(portfolio, save_snapshot=True):
    """Save portfolio snapshot to history with timestamp."""
    if not save_snapshot:
        return
    
    history = load_portfolio_history()
    timestamp = datetime.now().isoformat()
    
    # Calculate current value for history
    total_value = 0.0
    holdings_detail = []
    for ticker, shares in portfolio.items():
        price_data = get_stock_price(ticker)
        if price_data["success"]:
            position_value = price_data["price"] * shares
            total_value += position_value
            holdings_detail.append({
                "ticker": ticker,
                "shares": shares,
                "price": price_data["price"],
                "value": position_value
            })
    
    snapshot = {
        "timestamp": timestamp,
        "portfolio": portfolio,
        "total_value": round(total_value, 2) if total_value > 0 else None,
        "holdings": holdings_detail
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


def get_stock_price(ticker: str) -> dict:
    """Fetches the current stock price for a given ticker symbol using Yahoo Finance."""
    try:
        ticker_obj = yf.Ticker(ticker)
        info = ticker_obj.info
        current_price = info.get("currentPrice", info.get("regularMarketPreviousClose"))
        
        if current_price is None:
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                current_price = hist["Close"].iloc[-1]
        
        fetched_at = datetime.now().isoformat()
        
        if current_price is not None:
            return {
                "ticker": ticker.upper(),
                "price": float(current_price),
                "currency": info.get("currency", "USD"),
                "company_name": info.get("longName", ticker.upper()),
                "sector": info.get("sector", "Unknown"),
                "market_cap": info.get("marketCap", None),
                "fetched_at": fetched_at,
                "success": True
            }
        else:
            return {"ticker": ticker.upper(), "error": "Could not retrieve price", "success": False, "fetched_at": fetched_at}
    except Exception as e:
        fetched_at = datetime.now().isoformat()
        return {"ticker": ticker.upper(), "error": str(e), "success": False, "fetched_at": fetched_at}


def check_price_freshness(prices_dict):
    """Check price freshness (less than 15 minutes = fresh)."""
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
            "is_fresh": is_fresh
        }
    return result


def get_stock_news(ticker: str, num_articles: int = 5) -> dict:
    """Fetches recent news for a specific stock (tries Yahoo RSS first, falls back to yfinance)."""
    try:
        import requests
        from xml.etree import ElementTree as ET
        
        # Try RSS first
        try:
            url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            root = ET.fromstring(response.content)
            items = root.findall("./channel/item")
            
            articles = []
            for item in items[:num_articles]:
                title = item.findtext("title", default="")
                link = item.findtext("link", default="")
                pub_date = item.findtext("pubDate", default="")
                
                if title:
                    articles.append({
                        "title": title,
                        "link": link,
                        "publisher": "Yahoo Finance",
                        "timestamp": pub_date,
                        "relevance_tier": 1
                    })
            
            if len(articles) >=1:
                has_valid_news = any(a.get("title") for a in articles)
                return {
                    "ticker": ticker.upper(),
                    "articles": articles,
                    "success": True,
                    "has_valid_headlines": has_valid_news
                }
        except Exception:
            pass
        
        # Fall back to yfinance news with tier logic
        ticker_obj = yf.Ticker(ticker)
        news_list = ticker_obj.news
        
        # Get ticker and company name for filtering
        price_data = get_stock_price(ticker)
        company_name = price_data.get("company_name", ticker.upper()) if price_data.get("success") else ticker.upper()
        
        # Get sector keywords (default if missing)
        sector_keywords = ["semiconductor", "ai chip", "technology", "tech stock"]
        if price_data.get("sector") == "Technology":
            sector_keywords.extend(["gpu", "microchip", "chip", "ai"])
        
        articles_tier1 = []  # Exact ticker match (e.g., NVDA)
        articles_tier2 = []  # Company name match (e.g., NVIDIA)
        articles_tier3 = []  # Sector keyword match (e.g., semiconductor)
        
        for item in news_list:
            # Extract content dict which holds the actual news
            content = item.get("content", {})
            title = content.get("title", "")
            link = content.get("clickThroughUrl", {}).get("url", content.get("canonicalUrl", {}).get("url", ""))
            publisher = content.get("provider", {}).get("displayName", "")
            timestamp = content.get("pubDate", "")
            
            # Validate headline is not empty
            if not title:
                # Try to fallback to summary or description if title missing
                title = content.get("summary", content.get("description", ""))
            
            if not title:
                continue
            
            title_lower = title.lower()
            ticker_lower = ticker.lower()
            company_lower = company_name.lower()
            
            article_dict = {
                "title": title,
                "link": link,
                "publisher": publisher,
                "timestamp": timestamp
            }
            
            # Check tiers in order
            if ticker_lower in title_lower:
                article_dict["relevance_tier"] = 1
                articles_tier1.append(article_dict)
            elif any(part in title_lower for part in company_lower.split()):
                article_dict["relevance_tier"] = 2
                articles_tier2.append(article_dict)
            elif any(kw in title_lower for kw in sector_keywords):
                article_dict["relevance_tier"] = 3
                articles_tier3.append(article_dict)
        
        # Combine tiers in order, up to num_articles total
        articles = []
        articles.extend(articles_tier1)
        if len(articles) < num_articles:
            articles.extend(articles_tier2)
        if len(articles) < num_articles:
            articles.extend(articles_tier3)
        articles = articles[:num_articles]
        
        # Validate at least some articles have headlines
        has_valid_news = any(a.get("title") for a in articles)
        
        return {
            "ticker": ticker.upper(),
            "articles": articles,
            "success": True,
            "has_valid_headlines": has_valid_news
        }
    except Exception as e:
        return {"ticker": ticker.upper(), "error": str(e), "success": False}


def get_portfolio_holdings() -> dict:
    """Fetches the current portfolio holdings."""
    portfolio = load_portfolio()
    return {"holdings": portfolio, "success": True}


def add_stock_to_portfolio(ticker: str, shares: int, save_snapshot=True) -> dict:
    """Add or update a stock in the portfolio."""
    try:
        shares = int(shares)
        if shares < 0:
            return {"error": "Shares cannot be negative", "success": False}
        
        portfolio = load_portfolio()
        ticker_upper = ticker.upper()
        
        if shares == 0:
            if ticker_upper in portfolio:
                del portfolio[ticker_upper]
                save_result = save_portfolio(portfolio, save_snapshot=save_snapshot)
                return {"message": f"Removed {ticker_upper} from portfolio", "success": save_result["success"]}
            else:
                return {"message": f"{ticker_upper} not in portfolio", "success": True}
        
        portfolio[ticker_upper] = portfolio.get(ticker_upper, 0) + shares
        save_result = save_portfolio(portfolio, save_snapshot=save_snapshot)
        return {"message": f"Updated portfolio: {ticker_upper} now has {portfolio[ticker_upper]} shares", "success": save_result["success"]}
    except ValueError:
        return {"error": "Shares must be an integer", "success": False}
    except Exception as e:
        return {"error": str(e), "success": False}


def get_portfolio_analysis() -> dict:
    """Get comprehensive analysis of the portfolio including total value and allocation."""
    try:
        portfolio = load_portfolio()
        if not portfolio:
            return {"error": "Portfolio is empty", "success": False}
        
        total_value = 0.0
        holdings_detail = []
        sectors = {}
        
        for ticker, shares in portfolio.items():
            price_data = get_stock_price(ticker)
            if price_data["success"]:
                position_value = price_data["price"] * shares
                total_value += position_value
                sector = price_data.get("sector", "Unknown")
                sectors[sector] = sectors.get(sector, 0) + position_value
                holdings_detail.append({
                    "ticker": ticker,
                    "shares": shares,
                    "price": price_data["price"],
                    "value": position_value,
                    "company_name": price_data["company_name"],
                    "sector": sector,
                    "currency": price_data["currency"]
                })
        
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
            "holdings": holdings_detail,
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
                "is_stale": abs(price_diff_pct) >5
            })
    
    return {
        "audit_results": audit_results,
        "has_stale_prices": has_stale_prices
    }


def get_ai_trend_stocks() -> dict:
    """Get a curated list of AI trend stocks to watch."""
    ai_trend_stocks = [
        {"ticker": "NVDA", "company": "NVIDIA Corporation", "reason": "GPU leader, AI training hardware"},
        {"ticker": "SMCI", "company": "Super Micro Computer", "reason": "AI infrastructure solutions"},
        {"ticker": "AMD", "company": "Advanced Micro Devices", "reason": "AI accelerators and CPUs"},
        {"ticker": "MSFT", "company": "Microsoft", "reason": "Azure AI, Copilot, OpenAI partnership"},
        {"ticker": "GOOGL", "company": "Alphabet (Google)", "reason": "Google AI, DeepMind, cloud AI"},
        {"ticker": "META", "company": "Meta Platforms", "reason": "AI research, Llama models"},
        {"ticker": "TSM", "company": "Taiwan Semiconductor", "reason": "AI chip manufacturing"},
        {"ticker": "PLTR", "company": "Palantir Technologies", "reason": "AI for enterprise analytics"},
        {"ticker": "SNOW", "company": "Snowflake", "reason": "AI data cloud platform"},
        {"ticker": "CRM", "company": "Salesforce", "reason": "Einstein AI, CRM AI integrations"}
    ]
    
    return {"ai_trend_stocks": ai_trend_stocks, "success": True}


def get_tools_definition():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_stock_price",
                "description": "Fetches real-time stock price, sector, market cap, and company info for a given ticker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "The stock ticker symbol (e.g., AAPL, NVDA)"
                        }
                    },
                    "required": ["ticker"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_stock_news",
                "description": "Fetches recent news articles for a stock ticker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "The stock ticker symbol (e.g., AAPL, NVDA)"
                        },
                        "num_articles": {
                            "type": "integer",
                            "description": "Number of news articles to fetch (default 5, max 20)"
                        }
                    },
                    "required": ["ticker"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_portfolio_holdings",
                "description": "Fetches the current portfolio holdings.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "add_stock_to_portfolio",
                "description": "Add, update, or remove a stock in the portfolio. Set shares to 0 to remove.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string", "description": "Stock ticker symbol"},
                        "shares": {"type": "integer", "description": "Number of shares (0 to remove)"}
                    },
                    "required": ["ticker", "shares"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_portfolio_analysis",
                "description": "Get comprehensive portfolio analysis including total value, allocation, and sector breakdown.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_portfolio_performance",
                "description": "Get historical performance of the portfolio over a specified number of days.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "days": {"type": "integer", "description": "Number of days to look back (default 30)"}
                    }
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_ai_trend_stocks",
                "description": "Get a curated list of key AI trend stocks with analysis of their relevance to AI.",
                "parameters": {"type": "object", "properties": {}}
            }
        }
    ]


def execute_tool(function_name, function_args):
    if function_name == "get_stock_price":
        return get_stock_price(**function_args)
    elif function_name == "get_stock_news":
        return get_stock_news(**function_args)
    elif function_name == "get_portfolio_holdings":
        return get_portfolio_holdings()
    elif function_name == "add_stock_to_portfolio":
        return add_stock_to_portfolio(**function_args)
    elif function_name == "get_portfolio_analysis":
        return get_portfolio_analysis()
    elif function_name == "get_portfolio_performance":
        return get_portfolio_performance(**function_args)
    elif function_name == "get_ai_trend_stocks":
        return get_ai_trend_stocks()
    else:
        return {"error": "Unknown tool", "success": False}


def process_single_question(question):
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    tools = get_tools_definition()
    
    messages = [
        {
            "role": "system",
            "content": """You are an expert, professional portfolio manager and investment advisor with deep knowledge of AI trends and market sentiment. Your goal is to provide accurate, timely, and actionable investment insights.

Key Principles:
1. **Professional & Sensitive**: Be cautious with advice, acknowledge risks, avoid overconfidence
2. **Accurate & Up-to-Date**: Always use available tools to fetch real-time data
3. **AI Trend Focused**: Pay special attention to AI-related developments and their market impact
4. **Sentiment Aware**: Consider news and market sentiment in your analysis
5. **Risk-Focused**: Always highlight both opportunities and risks

Always explain your reasoning clearly and provide balanced perspectives.
"""
        },
        {"role": "user", "content": question}
    ]
    
    while True:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        assistant_message = response.choices[0].message
        messages.append(assistant_message)
        
        if not assistant_message.tool_calls:
            return assistant_message.content
        
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
            print(f"[Agent is calling tool: {function_name}]")
            tool_response = execute_tool(function_name, function_args)
            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": function_name,
                "content": json.dumps(tool_response)
            })


def run_interactive_mode():
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    tools = get_tools_definition()
    
    messages = [
        {
            "role": "system",
            "content": """You are an expert, professional portfolio manager and investment advisor with deep knowledge of AI trends and market sentiment. Your goal is to provide accurate, timely, and actionable investment insights.

Key Principles:
1. **Professional & Sensitive**: Be cautious with advice, acknowledge risks, avoid overconfidence
2. **Accurate & Up-to-Date**: Always use available tools to fetch real-time data
3. **AI Trend Focused**: Pay special attention to AI-related developments and their market impact
4. **Sentiment Aware**: Consider news and market sentiment in your analysis
5. **Risk-Focused**: Always highlight both opportunities and risks

Always explain your reasoning clearly and provide balanced perspectives.
"""
        }
    ]
    
    print("="*60)
    print("🚀 Professional AI Trend Portfolio Agent")
    print("="*60)
    print("Enhanced Features:")
    print("- Real-time AI trend tracking & sentiment analysis")
    print("- Portfolio performance history & sector breakdown")
    print("- News & market sentiment integration")
    print("- Professional risk assessment & recommendations")
    print("\nExample questions:")
    print("- 'Analyze my portfolio with AI trend sentiment'")
    print("- 'Show recent news for NVDA'")
    print("- 'What are the top AI trend stocks to watch?'")
    print("- 'How has my portfolio performed in the last 30 days?'")
    print("\nType 'exit' to quit")
    print("="*60)
    
    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() == "exit":
            print("\nGoodbye! Happy investing! 📈")
            break
            
        messages.append({"role": "user", "content": user_input})
        
        while True:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            assistant_message = response.choices[0].message
            messages.append(assistant_message)
            
            if not assistant_message.tool_calls:
                print(f"\nAgent: {assistant_message.content}")
                break
            
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                print(f"\n[Agent is calling tool: {function_name}]")
                tool_response = execute_tool(function_name, function_args)
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(tool_response)
                })


def run_facts_pass() -> dict:
    """Pass 1: Collect and assemble facts-only JSON summary"""
    from datetime import datetime, timezone
    
    snapshot_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    data_quality_flags = []
    holdings = []
    all_prices = {}
    
    # Step 1: Load portfolio
    portfolio = load_portfolio()
    if not portfolio:
        data_quality_flags.append("portfolio_empty")
        return {"snapshot_ts": snapshot_ts, "holdings": [], "portfolio": {}, "data_quality_flags": data_quality_flags}
    
    total_value = 0.0
    sector_totals = {}
    weights = {}
    holdings_list = list(portfolio.items())
    
    # Sort by shares/value descending for top holdings
    for ticker, shares in holdings_list:
        price_data = get_stock_price(ticker)
        all_prices[ticker] = price_data
        if not price_data.get("success"):
            data_quality_flags.append(f"price_missing_for_{ticker}")
            continue
        
        value = price_data["price"] * shares
        total_value += value
        
        holding = {
            "ticker": price_data["ticker"],
            "company": price_data["company_name"],
            "shares": shares,
            "price": price_data["price"],
            "value": value,
            "sector": price_data["sector"]
        }
        holdings.append(holding)
        
        sector = price_data.get("sector", "Unknown")
        sector_totals[sector] = sector_totals.get(sector, 0.0) + value
    
    # Check price freshness
    price_freshness = check_price_freshness(all_prices)
    
    # Calculate weights
    if total_value > 0:
        for holding in holdings:
            weights[holding["ticker"]] = holding["value"] / total_value
    
    # Sector weights
    sector_weights = {}
    if total_value > 0:
        for sector, val in sector_totals.items():
            sector_weights[sector] = val / total_value
    
    # Performance data
    performance = None
    audit_start = None
    has_stale_start_prices = False
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
                news.append({
                    "ticker": holding["ticker"],
                    "headline": article.get("title", ""),
                    "source": article.get("publisher", ""),
                    "published_at": article.get("timestamp", ""),
                    "url": article.get("link", "")
                })
        else:
            data_quality_flags.append(f"news_missing_for_{holding['ticker']}")
    
    # Final facts JSON
    facts = {
        "snapshot_ts": snapshot_ts,
        "holdings": holdings,
        "portfolio": {
            "total_value": total_value,
            "weights": weights,
            "sector_weights": sector_weights
        },
        "performance": performance,
        "ai_trend_stocks": ai_trend_list,
        "news": news,
        "start_snapshot_audit": audit_start,
        "price_freshness": price_freshness,
        "data_quality_flags": data_quality_flags
    }
    
    return facts


def run_critic_pass(facts: dict, deepseek_client=None) -> dict:
    """Pass 2: Validate facts using DeepSeek Critic (falls back to local checks if no client)"""
    from datetime import datetime
    issues = []
    passed = True
    
    # First: Run the existing local validation checks
    data_quality_flags = facts.get("data_quality_flags", []).copy()
    
    # 1. Consistency Checks
    total_value_from_holdings = sum(h["value"] for h in facts.get("holdings", []))
    total_value = facts.get("portfolio", {}).get("total_value", 0)
    if abs(total_value_from_holdings - total_value) > 0.01:
        issues.append(f"Total value mismatch: holdings sum to ${total_value_from_holdings:.2f}, reported as ${total_value:.2f}")
    
    weights = facts.get("portfolio", {}).get("weights", {})
    sum_weights = sum(weights.values())
    if abs(sum_weights - 1.0) > 0.001:
        issues.append(f"Weights sum to {sum_weights:.4f}, should be 1.0")
    
    sector_weights = facts.get("portfolio", {}).get("sector_weights", {})
    if sector_weights:
        sum_sector_weights = sum(sector_weights.values())
        if abs(sum_sector_weights - 1.0) > 0.001:
            issues.append(f"Sector weights sum to {sum_sector_weights:.4f}, should be 1.0")
    
    # 2. Risk Metrics
    # Max single weight
    if weights:
        sorted_items = sorted(weights.items(), key=lambda x: -x[1])
        sorted_weights = sorted(weights.values(), reverse=True)
        max_weight = sorted_weights[0] if sorted_weights else 0
        top_2_weight = sum(sorted_weights[:2]) if len(sorted_weights) >=2 else 0
        
        # Herfindahl Index
        hhi = sum(w ** 2 for w in weights.values())
        
        if hhi < 0.15:
            concentration = "well diversified"
        elif 0.15 <= hhi <= 0.25:
            concentration = "moderately concentrated"
        else:
            concentration = "highly concentrated"
    else:
        max_weight = 0
        top_2_weight = 0
        hhi = 0
        concentration = "well diversified"
    
    # Check other local issues
    # Check for stale prices
    price_freshness = facts.get("price_freshness", {})
    for ticker, data in price_freshness.items():
        if not data.get("is_fresh", True):
            issues.append(f"Stale price for {ticker}: last updated {data.get('age_minutes'):.1f} minutes ago")
    
    # Check performance period_days ==0
    performance = facts.get("performance", {})
    if performance.get("period_days", 0) == 0 and not (performance.get("snapshots_available", 1) ==1):
        issues.append("Period days is zero and not explicitly marked as baseline snapshot")
    
    # Check HHI >0.3 (we'll flag as an issue)
    if hhi > 0.3:
        issues.append(f"High concentration risk (HHI = {hhi:.4f}) without a rebalance recommendation")
    
    # Check news articles for relevance (local check first)
    holdings_tickers = [h.get("ticker").upper() for h in facts.get("holdings", [])]
    for news_item in facts.get("news", []):
        headline = news_item.get("headline", "").upper()
        ticker = news_item.get("ticker", "").upper()
        if ticker not in holdings_tickers:
            issues.append(f"News article for {ticker} not in portfolio holdings: {headline}")
    
    # Now try DeepSeek if client available
    if deepseek_client:
        try:
            system_prompt = """You are a financial data critic. Review this portfolio facts JSON and return a JSON object with two fields:
- passed: true/false
- issues: list of strings describing specific problems found
Check for: stale prices (age > 15 min), news articles with no relevance to the portfolio tickers, HHI > 0.3 without a rebalance recommendation, period_days == 0 without a baseline message, any value inconsistencies."""
            
            user_prompt = f"Facts JSON:\n{json.dumps(facts, indent=2, default=str)}"
            
            response = deepseek_client.chat.completions.create(
                model="deepseek-reasoner",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            # Parse response
            critic_json = json.loads(response.choices[0].message.content)
            ai_passed = critic_json.get("passed", False)
            ai_issues = critic_json.get("issues", [])
            
            # Merge issues
            if ai_issues:
                issues.extend(ai_issues)
            passed = passed and ai_passed
            
        except Exception as e:
            print(f"[WARN] DeepSeek Critic unavailable: {str(e)}")
    
    # Finalize passed flag
    passed = passed and len(issues) ==0
    
    # Add risk metrics to facts out
    facts_out = facts.copy()
    facts_out["data_quality_flags"] = data_quality_flags
    facts_out["risk_metrics"] = {
        "max_single_weight": max_weight,
        "top_2_weight_sum": top_2_weight,
        "hhi": hhi,
        "concentration_class": concentration
    }
    
    return {
        "passed": passed,
        "issues": issues,
        "validated_facts": facts_out
    }


def format_critic_issues(issues):
    """Format critic issues for user display"""
    issue_str = "\n".join([f"- {i}" for i in issues])
    return f"[CRITIC BLOCKED] Report generation paused. Issues found:\n{issue_str}"


def generate_narrative_report(facts: dict) -> str:
    """Pass3: Generate professional report from validated facts only - no fabrications!"""
    from datetime import datetime
    
    # Critical data check first
    critical_missing = any(flag.startswith("price_missing_for") or flag == "portfolio_empty" for flag in facts.get("data_quality_flags", []))
    if critical_missing:
        missing = ", ".join(f for f in facts["data_quality_flags"] if f in ["portfolio_empty"] or f.startswith("price_missing_for"))
        return f"I'm missing critical data ({missing}) and can't reliably analyze your portfolio. Please rerun the agent or add those data sources."
    
    snapshot_ts = facts["snapshot_ts"]
    holdings = facts["holdings"]
    portfolio = facts["portfolio"]
    performance = facts.get("performance")
    risk = facts.get("risk_metrics", {})
    news = facts.get("news", [])
    ai_trend = facts.get("ai_trend_stocks", [])
    price_freshness = facts.get("price_freshness", {})
    
    report_parts = []
    report_parts.append(f"Prices and values as of {snapshot_ts}.")
    
    # Check for stale prices and print warnings
    for ticker, freshness in price_freshness.items():
        if not freshness.get("is_fresh", True):
            age = freshness.get("age_minutes", 0)
            report_parts.append(f"[WARN] Stale price for {ticker}: last updated {age}m ago")
    
    report_parts.append("\n# Portfolio Snapshot\n")
    
    # Holdings table
    report_parts.append("| Ticker | Company | Shares | Price | Value | Weight |")
    report_parts.append("|--------|---------|--------|-------|-------|--------|")
    for h in holdings:
        w = portfolio["weights"].get(h["ticker"],0)
        w_pct = round(w*100,2)
        report_parts.append(f"| {h['ticker']} | {h['company']} | {h['shares']} | ${h['price']:.2f} | ${h['value']:.2f} | {w_pct}% |")
    report_parts.append(f"\n**Total Value**: ${portfolio['total_value']:.2f}")
    
    # Risk section
    report_parts.append("\n## Risk Assessment")
    max_pct = round(risk.get("max_single_weight",0)*100, 2)
    top2_pct = round(risk.get("top_2_weight_sum",0)*100, 2)
    hhi = round(risk.get("hhi",0), 4)
    concentration = risk.get("concentration_class")
    report_parts.append(f"- **Max single-name weight**: {max_pct}% ({'⚠️ Breaches 30% concentration limit' if max_pct > 30 else 'Within reasonable'})")
    report_parts.append(f"- **Top-2 weight sum**: {top2_pct}%")
    report_parts.append(f"- **HHI concentration**: {hhi} ({concentration})")
    
    sector_str = ", ".join([f"{s}: {round(v*100, 2)}%" for s,v in portfolio["sector_weights"].items()])
    report_parts.append(f"- **Sector concentration**: {sector_str}")
    
    # Performance
    if performance:
        report_parts.append("\n## Performance")
        pd = performance
        
        if pd.get("snapshots_available", 0) == 1:
            # Only one snapshot
            end_date = pd.get("end_date", "")
            report_parts.append(f"No historical comparison available yet — this is your baseline snapshot as of {end_date}.")
            report_parts.append("\nRun the agent again tomorrow to see performance.")
        else:
            days = pd.get("period_days")
            report_parts.append(f"Period: {pd.get('start_date')} → {pd.get('end_date')} ({days:.2f} days)")
            report_parts.append(f"- Start: ${pd['start_value']:.2f}")
            report_parts.append(f"- End: ${pd['end_value']:.2f}")
            report_parts.append(f"- Return: ${pd['absolute_return']:.2f} ({pd['percent_return']:.2f}%)")
            if days < 1:
                report_parts.append("[WARN] Short window: return reflects less than 1 trading day")
            
            # Show stale snapshot warning and audit
            if "start_snapshot_stale_prices" in facts.get("data_quality_flags", []):
                report_parts.append("\n[WARN] Start snapshot prices may be stale — auditing...")
                audit = facts.get("start_snapshot_audit", [])
                report_parts.append("\n### Price Audit")
                for entry in audit:
                    stale_mark = "⚠️ " if entry.get("is_stale", False) else ""
                    report_parts.append(
                        f"- {entry['ticker']}: snapshot=${entry['snapshot_price']:.2f} vs. current=${entry['current_price']:.2f} ({entry['diff_pct']:.1f}%) {stale_mark}"
                    )
    
    # News & AI Trend
    report_parts.append("\n## News & AI Trends")
    if news:
        for n in news:
            if n.get("headline"):
                report_parts.append(f"- **{n['ticker']}**: {n['headline']} [{n['source']}]")
    
    ai_in_portfolio = set(h['ticker'] for h in holdings)
    ai_trend_in_portfolio = [s for s in ai_trend if s['ticker'] in ai_in_portfolio]
    ai_trend_not_in = [s for s in ai_trend if s['ticker'] not in ai_in_portfolio]
    if ai_trend_in_portfolio:
        report_parts.append(f"\nAI trend holdings in portfolio: {', '.join(s['ticker'] for s in ai_trend_in_portfolio)}")
    if ai_trend_not_in:
        report_parts.append(f"Missing AI trend exposures: {', '.join(s['ticker'] for s in ai_trend_not_in[:3])}")
    
    # Data quality warnings
    if facts["data_quality_flags"]:
        report_parts.append(f"\n---\n## Data Quality Warnings")
        for flag in facts["data_quality_flags"]:
            report_parts.append(f"- {flag}")
    
    return "\n".join(report_parts)


def run_reliability_mode():
    """Run full three-pass reliability-focused analysis"""
    print("🔍 Running reliability-focused analysis...")
    print("   Phase 1: Collecting facts...")
    facts = run_facts_pass()
    print("✅ Facts collected!")
    
    print("🔍 Phase 2: Critic pass validating & computing risk...")
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    critic_result = run_critic_pass(facts, deepseek_client=client)
    print("✅ Critic pass done!")
    
    if not critic_result["passed"]:
        print("\n" + format_critic_issues(critic_result["issues"]))
        return None
    
    validated_facts = critic_result["validated_facts"]
    print("📝 Phase3: Generating report...")
    report = generate_narrative_report(validated_facts)
    
    print("\n" + "="*60)
    print("📊 Reliability Analysis Report")
    print("="*60)
    print(report)
    print("="*60)
    
    # Also save facts JSON for audit
    with open("last_facts.json", "w") as f:
        json.dump(validated_facts, f, indent=2, default=str)
    print("   Facts saved to last_facts.json for audit.")
    return validated_facts


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        keep = 1
        if len(sys.argv) > 2 and sys.argv[2].isdigit():
            keep = int(sys.argv[2])
        reset_performance_history(keep)
    elif len(sys.argv) > 1 and sys.argv[1] == "--reliability":
        run_reliability_mode()
    elif len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
        print(f"You: {question}")
        answer = process_single_question(question)
        print(f"\nAgent: {answer}")
    else:
        run_interactive_mode()
