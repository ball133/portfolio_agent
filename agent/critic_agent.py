
from openai import OpenAI
import os, json, re
from tools.risk import compute_risk_metrics

_client = None
_critic_system_prompt = None


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("[ERROR] DEEPSEEK_API_KEY not set. Add to .env")
        _client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    return _client


def _get_critic_system_prompt():
    global _critic_system_prompt
    if _critic_system_prompt is None:
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts",
            "critic_system.txt",
        )
        with open(prompt_path, "r", encoding="utf-8") as prompt_file:
            _critic_system_prompt = prompt_file.read()
    return _critic_system_prompt


def run_critic_pass(facts: dict, report: str = "", deepseek_client=None) -> dict:
    if deepseek_client:
        client = deepseek_client
    else:
        client = _get_client()
    # First run the existing local checks to preserve functionality
    issues = []
    passed = True

    data_quality_flags = facts.get("data_quality_flags", []).copy()

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

    risk_metrics = facts.get("risk_metrics") or compute_risk_metrics(weights)
    hhi = risk_metrics["hhi"]
    rebalance_note = (
        facts.get("rebalance_note")
        or " ".join(facts.get("rebalance_recommendations", []))
    ).strip()

    price_freshness = facts.get("price_freshness", {})
    for ticker, data in price_freshness.items():
        if data.get("is_mock"):
            issues.append(f"Mock price used for {ticker}")
        if not data.get("is_fresh", True):
            issues.append(f"Stale price for {ticker}: last updated {data.get('age_minutes'):.1f} minutes ago")

    performance = facts.get("performance") or {}
    if performance.get("period_days", 0) == 0 and not (performance.get("snapshots_available", 1) == 1):
        issues.append("Period days is zero and not explicitly marked as baseline snapshot")

    if hhi > 0.3 and not rebalance_note:
        issues.append(f"High concentration risk (HHI = {hhi:.4f}) without a rebalance recommendation")

    holdings_tickers = [h.get("ticker").upper() for h in facts.get("holdings", [])]
    for news_item in facts.get("news", []):
        headline = news_item.get("headline", "").upper()
        ticker = news_item.get("ticker", "").upper()
        if ticker not in holdings_tickers:
            issues.append(f"News article for {ticker} not in portfolio holdings: {headline}")

    # Now run DeepSeek Critic on the REPORT for the new rules if report is provided
    if report:
        user_content = f"FACTS:\n{json.dumps(facts, indent=2)}\n\nREPORT:\n{report}"
    else:
        user_content = json.dumps(facts, indent=2)
    resp = client.chat.completions.create(
        model="deepseek-reasoner",
        messages=[
            {"role": "system", "content": _get_critic_system_prompt()},
            {"role": "user",   "content": user_content}
        ]
    )
    raw = resp.choices[0].message.content
    try:
        critic_json = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"```(?:json)?\s*([\s\S]+?)```", raw)
        critic_json = json.loads(match.group(1)) if match else {"passed": False, "issues": [raw]}

    ai_issues = critic_json.get("issues", [])
    if ai_issues:
        issues.extend(ai_issues)
    passed = passed and critic_json.get("passed", False) and len(issues) == 0

    facts_out = facts.copy()
    facts_out["data_quality_flags"] = data_quality_flags
    facts_out["risk_metrics"] = risk_metrics

    return {
        "passed": passed,
        "issues": issues,
        "validated_facts": facts_out
    }


def format_critic_issues(issues):
    issue_str = "\n".join([f"- {i}" for i in issues])
    return f"[CRITIC BLOCKED] Report generation paused. Issues found:\n{issue_str}"
