#!/usr/bin/env python3
# LEGACY - superseded by tests/ directory. Do not run.
"""Test fixed get_stock_news"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from portfolio_agent import get_stock_news


def main():
    print("=== Testing get_stock_news for NVDA ===\n")
    result = get_stock_news("NVDA", 3)
    articles = result.get("articles", [])

    print(f"Success: {result.get('success')}")
    print(f"Has valid headlines: {result.get('has_valid_headlines')}")
    print(f"\nArticles ({len(articles)}):")
    for i, article in enumerate(articles, 1):
        print(f"\n{i}. {article.get('title', '')}")
        print(f"   Publisher: {article.get('publisher', article.get('source', ''))}")
        print(f"   Link: {article.get('link', article.get('url', ''))}")


if __name__ == "__main__":
    main()
