#!/usr/bin/env python3
"""Run the portfolio agent from command line."""
import sys
import os

# Add project root directory to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.pipeline import (
    run_reliability_mode,
    process_single_question,
    run_interactive_mode
)
from tools.portfolio import reset_performance_history


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        keep = 0
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


if __name__ == "__main__":
    main()
