"""Main orchestrator for portfolio agent (facts → critic → narrative)."""
import json
import os
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from agent.facts_agent import run_facts_pass
from agent.critic_agent import run_critic_pass, format_critic_issues
from agent.narrative_agent import generate_narrative_report
from tools.prices import get_stock_price
from tools.news import get_stock_news
from tools.portfolio import add_stock_to_portfolio, reset_performance_history
from tools.performance import get_portfolio_analysis, get_portfolio_performance, get_portfolio_holdings
from tools.ai_trends import get_ai_trend_stocks
from config.settings import LOOP_STATE_FILE, MAX_ITERATIONS, TOKEN_BUDGET_WARNING, STATE_DIR

load_dotenv()


def validate_environment():
    """Check if required API keys are present."""
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    if not deepseek_key:
        raise RuntimeError("[ERROR] DEEPSEEK_API_KEY not set. Add it to .env")


def get_tools_definition():
    return [
        {
            "type": "function",
            "function": {
                "name": "get_stock_price",
                "description": "Fetches current stock price, sector, market cap, company info for given ticker.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "ticker": {
                            "type": "string",
                            "description": "Stock ticker symbol (e.g., AAPL, NVDA)"
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
                "description": "Fetches recent news for a stock ticker.",
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
                "description": "Get comprehensive portfolio analysis: total value, allocation, sector breakdown.",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_portfolio_performance",
                "description": "Get historical performance of portfolio over N days.",
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
                "description": "Get a curated list of key AI trend stocks.",
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
    validate_environment()
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    client = OpenAI(api_key=deepseek_key, base_url=deepseek_base_url)
    tools = get_tools_definition()

    messages = [
        {
            "role": "system",
            "content": "You are an expert professional portfolio manager and investment advisor with deep knowledge of AI trends and market sentiment. Your goal is to provide accurate, timely, actionable investment insights.\n\nKey Principles:\n1. Professional and Sensitive: Be cautious with advice, acknowledge risks, avoid overconfidence\n2. Accurate & Up-to-Date: Always use available tools to fetch real-time data\n3. AI Trend Focused: Pay special attention to AI-related developments and their market impact\n4. Sentiment Aware: Consider news and market sentiment in your analysis\n5. Risk-Focused: Always highlight both opportunities and risks\n\nAlways explain your reasoning clearly and provide balanced perspectives."
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
    validate_environment()
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")
    deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    client = OpenAI(api_key=deepseek_key, base_url=deepseek_base_url)
    tools = get_tools_definition()

    messages = [
        {
            "role": "system",
            "content": "You are an expert professional portfolio manager and investment advisor with deep knowledge of AI trends and market sentiment. Your goal is to provide accurate, timely, actionable investment insights.\n\nKey Principles:\n1. Professional and Sensitive: Be cautious with advice, acknowledge risks, avoid overconfidence\n2. Accurate & Up-to-Date: Always use available tools to fetch real-time data\n3. AI Trend Focused: Pay special attention to AI-related developments and their market impact\n4. Sentiment Aware: Consider news and market sentiment in your analysis\n5. Risk-Focused: Always highlight both opportunities and risks\n\nAlways explain your reasoning clearly and provide balanced perspectives."
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
    print("- Analyze my portfolio with AI trend sentiment")
    print("- Show recent news for NVDA")
    print("- What are the top AI trend stocks to watch?")
    print("- How has my portfolio performed in the last 30 days?")
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


def _write_loop_state(records):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOOP_STATE_FILE, "w") as f:
        json.dump(records, f, indent=2, default=str)


def _read_loop_state():
    if os.path.exists(LOOP_STATE_FILE):
        with open(LOOP_STATE_FILE, "r") as f:
            return json.load(f)
    return []


def _analyze_issues_for_action(issues):
    action = "retry"
    issue_str = " ".join(issues).lower()

    if "stale" in issue_str and "price" in issue_str:
        action = "retried prices with fresh fetch"
    elif "stale" in issue_str and "news" in issue_str:
        action = "retried news with alternative fallback sources"
    elif "not relevant" in issue_str or "news article" in issue_str:
        action = "retried news with stricter relevance filtering"
    elif "hhi" in issue_str or "concentration" in issue_str:
        action = "recomputed risk metrics"

    return action


def _assess_facts_quality(facts):
    quality = {}
    news_tiers = [a.get("relevance_tier", 3) for a in facts.get("news", [])]
    quality["news_tier"] = max(news_tiers) if news_tiers else 3
    price_freshness = facts.get("price_freshness", {})
    all_fresh = all(data.get("is_fresh", True) for data in price_freshness.values())
    quality["prices_fresh"] = all_fresh
    return quality


def run_reliability_mode(deepseek_client=None):
    """Run reliability-focused analysis with Loop framework (facts → critic → narrative)."""
    if not deepseek_client:
        validate_environment()
    
    loop_records = []
    iteration = 1
    last_issues = []

    if deepseek_client:
        client = deepseek_client
    else:
        deepseek_key = os.getenv("DEEPSEEK_API_KEY")
        deepseek_base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        client = OpenAI(api_key=deepseek_key, base_url=deepseek_base_url)

    while iteration <= MAX_ITERATIONS:
        print(f"🔍 [Iteration {iteration}] Running reliability-focused analysis...")
        print("   Phase 1: Collecting facts...")
        facts = run_facts_pass()
        print("✅ Facts collected!")

        print("🔍 Phase 2: Critic pass validating & computing risk...")
        critic_result = run_critic_pass(facts, deepseek_client=client)
        print("✅ Critic pass done!")

        facts_quality = _assess_facts_quality(facts)
        critic_verdict = "passed" if critic_result["passed"] else "failed"
        current_issues = critic_result["issues"]
        last_issues = current_issues
        action_taken = _analyze_issues_for_action(current_issues)
        next_iteration = iteration + 1 if not critic_result["passed"] else None

        iteration_record = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "facts_quality": facts_quality,
            "critic_verdict": critic_verdict,
            "issues": current_issues,
            "action_taken": action_taken,
            "next_iteration": next_iteration
        }
        loop_records.append(iteration_record)
        _write_loop_state(loop_records)

        if critic_result["passed"]:
            validated_facts = critic_result["validated_facts"]
            print("📝 Phase3: Generating report...")
            report = generate_narrative_report(validated_facts)

            print("\n" + "="*60)
            print("📊 Reliability Analysis Report")
            print("="*60)
            print(report)
            print("="*60)

            last_facts_path = os.path.join(STATE_DIR, "last_facts.json")
            with open(last_facts_path, "w") as f:
                json.dump(validated_facts, f, indent=2, default=str)
            print("   Facts saved to last_facts.json for audit.")

            final_record = {
                "final_iteration": iteration,
                "status": "PASSED",
                "timestamp": datetime.now().isoformat()
            }
            loop_records.append(final_record)
            _write_loop_state(loop_records)

            return validated_facts

        if iteration >= MAX_ITERATIONS:
            final_record = {
                "final_iteration": iteration,
                "status": "STOPPED_MAX_ITERATIONS",
                "last_issues": last_issues,
                "timestamp": datetime.now().isoformat()
            }
            loop_records.append(final_record)
            _write_loop_state(loop_records)

            print("\n" + format_critic_issues(last_issues))
            msg = f"[LOOP STOPPED] Could not produce a verified report after {MAX_ITERATIONS} iterations. Last issues: {last_issues}"
            print(msg)
            return None

        print(f"   Issues found: {current_issues}")
        print(f"   Taking action: {action_taken}, retrying...")
        iteration += 1

    return None
