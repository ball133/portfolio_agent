#!/usr/bin/env python3
"""Debug Yahoo Finance news structure"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import yfinance as yf
import pprint

ticker = "NVDA"

print(f"=== DEBUG: Fetching news for {ticker} ===\n")
ticker_obj = yf.Ticker(ticker)
news = ticker_obj.news

print(f"Number of news items: {len(news)}")
print(f"\n=== Raw news item (first one): ===")

if news:
    first_item = news[0]
    print(f"\ntype: {type(first_item)}")
    print(f"\nAll keys: {list(first_item.keys())}")
    print(f"\npprint dump:\n")
    pprint.pprint(first_item)
