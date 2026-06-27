"""Generate professional report from validated facts only - no fabrications!"""


def generate_narrative_report(facts: dict) -> str:
    """Pass 3: Generate professional report from validated facts only - no fabrications!"""
    # Critical data check first
    critical_missing = any(flag.startswith("price_missing_for") or flag == "portfolio_empty" for flag in facts.get("data_quality_flags", []))
    if critical_missing:
        missing = ", ".join(f for f in facts["data_quality_flags"] if f in ["portfolio_empty"] or f.startswith("price_missing_for"))
        return f"I'm missing critical data ({missing}) and can't reliably analyze your portfolio. Please rerun the agent or add those data sources."

    snapshot_ts = facts["snapshot_ts"]
    holdings = facts["holdings"]
    hk_holdings = facts.get("hk_holdings", [])
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
    report_parts.append("| Ticker | Company | Shares | Price (USD) | Value (USD) | Weight |")
    report_parts.append("|--------|---------|--------|-------------|-------------|--------|")
    for h in holdings:
        w = portfolio["weights"].get(h["ticker"], 0)
        w_pct = round(w * 100, 2)
        report_parts.append(f"| {h['ticker']} | {h['company']} | {h['shares']} | ${h['price']:.2f} | ${h['value']:.2f} | {w_pct}% |")
    report_parts.append(f"\n**Total Value**: ${portfolio['total_value']:.2f}")

    if hk_holdings:
        report_parts.append("\n## HK Holdings (HKD)")
        report_parts.append("| Ticker | Company | Shares | Price (HKD) | Value (HKD) |")
        report_parts.append("|--------|---------|--------|-------------|-------------|")
        for holding in hk_holdings:
            report_parts.append(
                f"| {holding['ticker']} | {holding['company']} | {holding['shares']} | HK${holding['price']:.2f} | HK${holding['value']:.2f} |"
            )
        report_parts.append(
            f"\n**HK Total Value (HKD)**: HK${portfolio.get('hk_total_value_hkd', 0):.2f}"
        )
    if portfolio.get("notes"):
        report_parts.append(f"\n**Portfolio Notes**: {portfolio['notes']}")

    # Risk section
    report_parts.append("\n## Risk Assessment")
    max_pct = round(risk.get("max_single_weight", 0) * 100, 2)
    top2_pct = round(risk.get("top_2_weight_sum", 0) * 100, 2)
    hhi = round(risk.get("hhi", 0), 4)
    concentration = risk.get("concentration_class")
    report_parts.append(f"- **Max single-name weight**: {max_pct}% ({'⚠️ Breaches 30% concentration limit' if max_pct > 30 else 'Within reasonable'})")
    report_parts.append(f"- **Top-2 weight sum**: {top2_pct}%")
    report_parts.append(f"- **HHI concentration**: {hhi} ({concentration})")

    sector_str = ", ".join([f"{s}: {round(v*100, 2)}%" for s, v in portfolio["sector_weights"].items()])
    report_parts.append(f"- **Sector concentration**: {sector_str}")

    rebalance_recommendations = facts.get("rebalance_recommendations", [])
    if rebalance_recommendations:
        report_parts.append("\n## Rebalance Recommendation")
        for recommendation in rebalance_recommendations:
            report_parts.append(f"- {recommendation}")

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
