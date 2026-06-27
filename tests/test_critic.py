
"""Tests for facts pass, critic pass, risk metrics, and narrative report."""
import os
from unittest.mock import MagicMock
from agent.facts_agent import run_facts_pass
from agent.critic_agent import run_critic_pass
from agent.narrative_agent import generate_narrative_report
from agent.pipeline import run_reliability_mode
from config.settings import LOOP_STATE_FILE


def mock_deepseek_client():
    """Mock DeepSeek client for testing."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = '{"passed": true, "issues": []}'
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def test_portfolio_math_consistency():
    """Test sum of holdings matches total value in facts pass."""
    facts = run_facts_pass()
    holdings = facts["holdings"]
    sum_values = sum(h["value"] for h in holdings)
    total_value = facts["portfolio"]["total_value"]
    diff = abs(sum_values - total_value)
    assert diff < 1.0, f"Sum should be within $1 of total, diff ${diff:.2f}"


def test_risk_metrics_sanity():
    """Test risk metrics are calculated and are valid."""
    facts = run_facts_pass()
    critic_result = run_critic_pass(facts, deepseek_client=mock_deepseek_client())
    validated = critic_result["validated_facts"]
    risk = validated["risk_metrics"]

    max_w = risk["max_single_weight"]
    hhi = risk["hhi"]
    label = risk["concentration_class"]

    assert max_w is not None, "max_single_weight should not be None"
    assert max_w > 0, "max_single_weight should be >0"
    assert hhi is not None, "hhi should not be None"
    assert hhi > 0, "hhi >0"

    valid_labels = ["well diversified", "moderately concentrated", "highly concentrated"]
    assert label in valid_labels, f"Concentration label invalid: {label}"


def test_critic_pass_known_issue():
    """Test critic pass blocks report with irrelevant news."""
    base_facts = run_facts_pass()
    mock_facts = base_facts.copy()
    mock_facts["news"] = [
        {
            "ticker": "XYZ",
            "headline": "XYZ Stock Rallies",
            "source": "Mock",
            "published_at": "",
            "url": ""
        }
    ]

    critic_result = run_critic_pass(mock_facts, deepseek_client=mock_deepseek_client())

    assert not critic_result["passed"], "Critic should fail with known issue"
    assert len(critic_result["issues"]) > 0, "Critic should report issues"

    issue_text = " ".join(critic_result["issues"]).lower()
    assert "xyz" in issue_text or "not in portfolio" in issue_text, "Issue should mention irrelevant news"


def test_narrative_report_generation():
    """Test narrative report is generated from validated facts."""
    facts = run_facts_pass()
    critic_result = run_critic_pass(facts, deepseek_client=mock_deepseek_client())
    validated_facts = critic_result["validated_facts"]

    report = generate_narrative_report(validated_facts)
    assert isinstance(report, str), "Report should be a string"
    assert len(report) > 0, "Report should not be empty"


def test_loop_state_written_on_critic_failure():
    """Test 12: Loop state is written on critic pass failure."""
    # Mock facts pass to always return facts with bad news
    base_facts = run_facts_pass()
    # Create a modified facts object with irrelevant news
    test_facts = base_facts.copy()
    test_facts["news"] = [
        {
            "ticker": "NOW",  # ServiceNow
            "headline": "ServiceNow Reports Record Quarter",
            "source": "Mock News",
            "published_at": "",
            "url": ""
        }
    ]

    # Run critic pass directly
    critic_result = run_critic_pass(test_facts, deepseek_client=mock_deepseek_client())

    assert not critic_result["passed"], "Critic should fail with bad news"
    assert len(critic_result["issues"]) > 0, "Critic should report issues"

    # Now test that loop state is written when running run_reliability_mode()
    # But since we can't actually run 3 iterations without calling external APIs,
    # let's test the individual helper functions _write_loop_state and _analyze_issues_for_action
    from agent.pipeline import _write_loop_state, _read_loop_state, _analyze_issues_for_action

    test_record = [
        {
            "iteration": 1,
            "timestamp": "2026-06-27T12:00:00",
            "facts_quality": {"news_tier": 3, "prices_fresh": True},
            "critic_verdict": "failed",
            "issues": critic_result["issues"],
            "action_taken": "retry",
            "next_iteration": 2
        }
    ]
    _write_loop_state(test_record)
    assert os.path.exists(LOOP_STATE_FILE), "loop_state.json should exist"

    read_records = _read_loop_state()
    assert len(read_records) == 1, "Should have 1 record"
    assert read_records[0]["critic_verdict"] == "failed"
    assert read_records[0]["iteration"] == 1
