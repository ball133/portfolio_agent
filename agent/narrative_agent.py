"""Generate professional report from validated facts only - no fabrications!"""
import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = None
_narrative_system_prompt = None


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("[ERROR] DEEPSEEK_API_KEY not set. Add to .env")
        _client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    return _client


def _get_narrative_system_prompt():
    global _narrative_system_prompt
    if _narrative_system_prompt is None:
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts",
            "narrative_system.txt",
        )
        with open(prompt_path, "r", encoding="utf-8") as prompt_file:
            _narrative_system_prompt = prompt_file.read()
    return _narrative_system_prompt


def generate_narrative_report(facts: dict, deepseek_client=None) -> str:
    """Pass 3: Generate professional report from validated facts only - no fabrications!"""
    # Critical data check first
    critical_missing = any(flag.startswith("price_missing_for") or flag == "portfolio_empty" for flag in facts.get("data_quality_flags", []))
    if critical_missing:
        missing = ", ".join(f for f in facts["data_quality_flags"] if f in ["portfolio_empty"] or f.startswith("price_missing_for"))
        return f"I'm missing critical data ({missing}) and can't reliably analyze your portfolio. Please rerun the agent or add those data sources."

    if deepseek_client:
        client = deepseek_client
    else:
        client = _get_client()

    system_prompt = _get_narrative_system_prompt()
    user_content = json.dumps(facts, indent=2)

    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_content}
        ],
        temperature=0.3
    )
    return resp.choices[0].message.content
