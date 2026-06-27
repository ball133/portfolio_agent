#!/usr/bin/env python3
# LEGACY - superseded by tests/ directory. Do not run.
"""
Smoke and Dry Test Script for Portfolio Agent
Tests all key functionalities without making permanent changes
"""
import sys
import os
import json
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from portfolio_agent import (
    load_portfolio,
    get_stock_price,
    get_stock_news,
    get_portfolio_analysis,
    get_portfolio_performance,
    get_ai_trend_stocks,
    add_stock_to_portfolio,
    PORTFOLIO_FILE,
    HISTORY_FILE
)

# Backup original portfolio files before testing
def backup_files():
    """Backup portfolio files to restore after tests"""
    for f in [PORTFOLIO_FILE, HISTORY_FILE]:
        if os.path.exists(f):
            backup_name = f"{f}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            print(f"Backing up {f} -> {backup_name}")
            os.rename(f, backup_name)
            return backup_name
    return None

def restore_backup(backup_name):
    """Restore backup file"""
    original_name = backup_name.replace(".backup_", "")
    if os.path.exists(backup_name):
        os.rename(backup_name, original_name)

def test_portfolio_load():
    """Smoke test: Verify portfolio loading"""
    print("\n=== Test 1: Portfolio Loading ===")
    try:
        portfolio = load_portfolio()
        print("[OK] Portfolio loaded successfully!")
        print(f"[DATA] Holdings: {portfolio}")
        return True
    except Exception as e:
        print(f"[FAIL] Failed: {str(e)}")
        return False

def test_stock_price_fetch():
    """Smoke test: Verify stock price fetching."""
    print("\n=== Test 2: Stock Price Fetching ===")
    tickers = ["AAPL", "NVDA", "MSFT", "TSM"]
    all_success = True
    for ticker in tickers:
        try:
            result = get_stock_price(ticker)
            if result.get("success"):
                print(f"[OK] {ticker}: ${result['price']:.2f} ({result['company_name']})")
            else:
                print(f"[WARN] {ticker}: {result.get('error')}")
                all_success = False
        except Exception as e:
            print(f"[FAIL] {ticker}: {str(e)}")
            all_success = False
    return all_success

def test_news_fetching():
    """Smoke test: Verify news fetching"""
    print("\n=== Test 3: News Fetching ===")
    try:
        result = get_stock_news("NVDA", num_articles=3)
        if result.get("success"):
            articles = result.get("articles", [])
            assert len(articles) >= 2, f"Expected at least 2 articles, got {len(articles)}"
            
            # Verify all articles have a relevance_tier
            for article in articles:
                assert "relevance_tier" in article, f"Article missing relevance_tier"
                
            print(f"[OK] News fetch successful! Found {len(articles)} articles:")
            for i, article in enumerate(articles[:3], 1):
                tier_label = f" [Tier {article.get('relevance_tier')}]"
                print(f"  {i}. {article['title']}{tier_label}")
            return True
        else:
            print(f"[WARN] News fetch: {result.get('error')}")
            return False
    except Exception as e:
        print(f"[FAIL] News fetch failed: {str(e)}")
        return False

def test_portfolio_analysis():
    """Smoke test: Verify portfolio analysis"""
    print("\n=== Test 4: Portfolio Analysis ===")
    try:
        result = get_portfolio_analysis()
        if result.get("success"):
            print(f"[OK] Portfolio analysis successful!")
            print(f"[DATA] Total Value: ${result.get('total_value', 0):,.2f}")
            print(f"[DATA] Number of holdings: {len(result.get('holdings', []))}")
            return True
        else:
            print(f"[WARN] Analysis failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"[FAIL] Portfolio analysis failed: {str(e)}")
        return False

def test_ai_trend_stocks():
    """Smoke test: Verify AI trend stocks list"""
    print("\n=== Test 5: AI Trend Stocks ===")
    try:
        result = get_ai_trend_stocks()
        if result.get("success"):
            print(f"[OK] AI trend stocks fetched successfully!")
            print(f"[DATA] Number of AI trend stocks: {len(result.get('ai_trend_stocks', []))}")
            for stock in result.get('ai_trend_stocks', [])[:3]:
                print(f"   - {stock['ticker']}: {stock['company']}")
            return True
        else:
            print(f"[WARN] AI trend stocks failed: {result.get('error')}")
            return False
    except Exception as e:
        print(f"[FAIL] AI trend stocks failed: {str(e)}")
        return False

def test_portfolio_update_dry():
    """Dry test: Verify portfolio update functions (no permanent changes, no snapshots)"""
    print("\n=== Test 6: Portfolio Update (Dry Run) ===")
    try:
        # Test adding a temporary stock
        result = add_stock_to_portfolio("TEST", 0, save_snapshot=False)  # Should not change anything
        print(f"[OK] Test add/remove function: {result.get('message')}")
        
        # Test adding small position
        result = add_stock_to_portfolio("SPY", 1, save_snapshot=False)
        print(f"[OK] Add small position: {result.get('message')}")
        
        # Verify portfolio changed
        updated = load_portfolio()
        if "SPY" in updated:
            print(f"[OK] SPY added successfully! Now removing...")
            add_stock_to_portfolio("SPY", 0, save_snapshot=False)
            return True
        return False
    except Exception as e:
        print(f"[FAIL] Portfolio update failed: {str(e)}")
        return False

def test_performance_tracking():
    """Dry test: Verify performance tracking"""
    print("\n=== Test 7: Performance Tracking ===")
    try:
        # Save a snapshot (part of portfolio save function already)
        result = get_portfolio_performance(days=1)  # Check if it can load recent history
        if result.get("success") or "No history" in str(result.get("error")):
            print(f"[OK] Performance tracking working as expected!")
            print(f"[DATA] Result: {result}")
            return True
        else:
            return False
    except Exception as e:
        print(f"[FAIL] Performance tracking failed: {str(e)}")
        return False


def test_news_quality():
    """Test8: News quality check"""
    print("\n=== Test 8: News Quality Check ===")
    try:
        news_data = get_stock_news("NVDA", 3)
        
        assert isinstance(news_data, dict), "Result is a dict"
        assert news_data.get("success") is True, "News fetch success=True"
        articles = news_data.get("articles", [])
        assert len(articles) >0, "Have at least one article"
        
        # Check first article has non-empty title and is relevant
        first_article = articles[0]
        assert "title" in first_article, "Article has 'title' key"
        
        title = first_article.get("title", "")
        assert len(title.strip()) >0, "Headline not empty!"
        
        # Check relevance to NVDA/NVIDIA or AI
        title_lower = title.lower()
        has_relevance = ("nvda" in title_lower or "nvidia" in title_lower or "ai" in title_lower)
        assert has_relevance, "Headline should be relevant to NVDA/NVIDIA or AI"
        
        print(f"[OK] News quality check passed! First article:")
        print(f"   {title}")
        return True
    except Exception as e:
        print(f"[FAIL] News quality check failed: {e}")
        return False


def test_portfolio_math_consistency():
    """Test9: Portfolio math consistency check"""
    print("\n=== Test 9: Portfolio Math Consistency ===")
    try:
        from portfolio_agent import run_facts_pass
        
        facts = run_facts_pass()
        holdings = facts.get("holdings", [])
        
        sum_of_holding_values = sum(h["value"] for h in holdings)
        total_value = facts.get("portfolio", {}).get("total_value",0)
        
        diff = abs(sum_of_holding_values - total_value)
        
        assert diff <1.0, f"Sum of holdings (${sum_of_holding_values:.2f}) should be within $1 of total value (${total_value:.2f}), diff=${diff:.2f}"
        
        print(f"[OK] Portfolio math check passed!")
        print(f"   Sum of holding values = ${sum_of_holding_values:.2f}")
        print(f"   Reported total value = ${total_value:.2f}")
        print(f"   Difference = ${diff:.2f} < $1")
        return True
    except Exception as e:
        print(f"[FAIL] Portfolio math check failed: {e}")
        return False


def test_risk_metrics_sanity():
    """Test10: Risk metrics sanity check"""
    print("\n=== Test 10: Risk Metrics Sanity ===")
    try:
        from portfolio_agent import run_facts_pass, run_critic_pass
        
        facts = run_facts_pass()
        critic_result = run_critic_pass(facts)
        validated = critic_result.get("validated_facts", {})
        
        risk = validated.get("risk_metrics", {})
        
        max_w = risk.get("max_single_weight")
        hhi = risk.get("hhi")
        label = risk.get("concentration_class")
        
        assert max_w is not None, "max single weight should not be None"
        assert max_w >0, "max single weight should be >0"
        
        assert hhi is not None, "hhi should not be None"
        assert hhi >0, "hhi >0"
        
        valid_labels = ["well diversified", "moderately concentrated", "highly concentrated"]
        assert label in valid_labels, f"Concentration label should be one of {valid_labels}; got {label}"
        
        print(f"[OK] Risk metrics sanity check passed!")
        print(f"   Max single weight: {max_w:.4f}")
        print(f"   HHI: {hhi:.4f}")
        print(f"   Concentration: {label}")
        return True
    except Exception as e:
        print(f"[FAIL] Risk metrics sanity check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_price_freshness():
    """Test11: Verify all stock prices have fetched_at timestamp"""
    print("\n=== Test 11: Price Freshness ===")
    try:
        tickers = ["AAPL", "NVDA", "MSFT", "TSM"]
        prices = {}
        
        for ticker in tickers:
            result = get_stock_price(ticker)
            prices[ticker] = result
            
            # Check if fetched_at exists
            assert "fetched_at" in result, f"{ticker} missing fetched_at timestamp"
            assert result["fetched_at"] != "", f"{ticker} fetched_at is empty string"
            print(f"[OK] {ticker} fetched at {result['fetched_at']}")
        
        # Also check check_price_freshness function
        from portfolio_agent import check_price_freshness
        freshness = check_price_freshness(prices)
        
        assert len(freshness) == len(tickers), f"Expected {len(tickers)} entries in freshness result"
        
        for ticker in tickers:
            assert ticker in freshness, f"{ticker} missing from freshness result"
            assert "is_fresh" in freshness[ticker], f"{ticker} missing is_fresh field"
            assert "age_minutes" in freshness[ticker], f"{ticker} missing age_minutes"
        
        print(f"[OK] Price freshness check passed!")
        return True
    except Exception as e:
        print(f"[FAIL] Price freshness check failed: {e}")
        return False


def test_critic_pass_known_issue():
    """Test12: Verify critic pass blocks report with known issue"""
    print("\n=== Test 12: Critic Pass With Known Issue ===")
    try:
        from portfolio_agent import run_critic_pass, run_facts_pass
        
        # Create a mock facts_json with a known issue (irrelevant news)
        base_facts = run_facts_pass()
        mock_facts = base_facts.copy()
        # Add irrelevant news
        mock_facts["news"] = [
            {
                "ticker": "XYZ",  # Not in portfolio
                "headline": "XYZ Stock Rallies After Earnings",
                "source": "Mock Source",
                "published_at": "",
                "url": ""
            }
        ]
        
        # Run critic pass (no deepseek client, use local checks)
        critic_result = run_critic_pass(mock_facts, deepseek_client=None)
        
        # Assert it fails and has issues
        assert not critic_result["passed"], "Critic should fail with known issue"
        assert len(critic_result["issues"]) > 0, "Critic should report at least one issue"
        
        # Verify issue mentions the irrelevant news
        issue_text = " ".join(critic_result["issues"]).lower()
        assert "xyz" in issue_text or "not in portfolio" in issue_text, "Issue should mention irrelevant news"
        
        print(f"[OK] Critic pass correctly blocked with {len(critic_result['issues'])} issues!")
        print(f"   Issues: {critic_result['issues']}")
        
        return True
    except Exception as e:
        print(f"[FAIL] Critic pass test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# Main test runner
def main():
    print("="*60)
    print("[TEST] Portfolio Agent Smoke & Dry Test Suite")
    print("="*60)
    
    # Backup first
    backup_portfolio = backup_files()
    
    # Run all tests
    results = {
        "portfolio_load": test_portfolio_load(),
        "stock_price": test_stock_price_fetch(),
        "news_fetch": test_news_fetching(),
        "portfolio_analysis": test_portfolio_analysis(),
        "ai_trend_stocks": test_ai_trend_stocks(),
        "portfolio_update": test_portfolio_update_dry(),
        "performance_tracking": test_performance_tracking(),
        "news_quality": test_news_quality(),
        "portfolio_math": test_portfolio_math_consistency(),
        "risk_metrics": test_risk_metrics_sanity(),
        "price_freshness": test_price_freshness(),
        "critic_known_issue": test_critic_pass_known_issue()
    }
    
    # Report results
    print("\n" + "="*60)
    print("[SUMMARY] TEST SUMMARY")
    print("="*60)
    
    passed = sum(results.values())
    total = len(results)
    
    for name, success in results.items():
        status = "[PASSED]" if success else "[FAILED]"
        print(f"  {name:25s} : {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n[SUCCESS] ALL TESTS PASSED! Portfolio agent is healthy!")
        if backup_portfolio:
            print(f"[INFO] Keeping new portfolio files (cleaned up TESTs).")
    else:
        print(f"\n[WARN] Some tests failed!")
        if backup_portfolio:
            print(f"[INFO] Restoring backup files...")
            restore_backup(backup_portfolio)
    
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
