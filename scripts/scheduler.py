#!/usr/bin/env python3
"""Simple scheduler for the reliability pipeline during US market hours."""
import os
import requests
import sys
import time
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from agent.narrative_agent import generate_narrative_report
from agent.pipeline import run_reliability_mode
from config.settings import LOG_DIR
from tools.telegram import send_telegram_message

US_HOLIDAYS_2026 = {
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-04-03",
    "2026-05-25",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
}


def is_us_market_hours() -> bool:
    """HKT 21:30-04:00 = US regular trading hours, excluding weekends/holidays."""
    now = datetime.now()
    if now.weekday() >= 5:
        return False

    date_str = now.strftime("%Y-%m-%d")
    if date_str in US_HOLIDAYS_2026:
        return False

    hour = now.hour
    minute = now.minute
    return (
        (hour == 21 and minute >= 30)
        or (hour >= 22)
        or (hour <= 3)
        or (hour == 4 and minute == 0)
    )


def run_pipeline_once(force: bool = False):
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d_%H-%M")
    if not force and not is_us_market_hours():
        print(f"[{now.strftime('%H:%M')}] Market closed - skipping one-off run")
        return None

    log_path = os.path.join(LOG_DIR, "agent_runs", f"{ts}.log")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    print(f"[{ts}] Running pipeline...")
    result = run_reliability_mode()
    if result:
        summary = generate_narrative_report(result)
    else:
        summary = "[SCHEDULER] Pipeline returned no verified result."
    with open(log_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(summary)
    
    # Send to Telegram if configured
    print(f"[{ts}] Sending report to Telegram...")
    telegram_result = send_telegram_message(summary)
    if telegram_result["success"]:
        print(f"[{ts}] Telegram report sent successfully!")
    else:
        print(f"[{ts}] Failed to send Telegram report: {telegram_result['error']}")
    
    print(f"[{ts}] Done -> {log_path}")
    return log_path


def run_scheduled_loop(interval_minutes: int = 60):
    _ = requests
    print(
        f"[SCHEDULER] Starting - runs every {interval_minutes}m during US market hours"
    )
    while True:
        now = datetime.now()
        if is_us_market_hours():
            run_pipeline_once(force=True)
        else:
            next_check = interval_minutes
            print(f"[{now.strftime('%H:%M')}] Market closed - next check in {next_check}m")
        time.sleep(interval_minutes * 60)


if __name__ == "__main__":
    try:
        if "--run-now" in sys.argv:
            run_pipeline_once(force=True)
        else:
            run_scheduled_loop(interval_minutes=60)
    except KeyboardInterrupt:
        print("\n[SCHEDULER] Stopped by user.")
