"""
End-to-end CLI: fetch real financials for a ticker (auto-detects US vs
India), then run the full 9-agent first pass + 12-turn debate + CIO
synthesis against that real data.

Usage:
    python run_analysis.py PLTR
    python run_analysis.py URBANCO --market India
"""

import argparse
import sys

from agents.prompts import AGENT_DISPLAY_NAMES
from agents.runner import run_committee
from orchestrator.analyze import fetch_and_format

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows defaults redirected stdout to cp1252


def print_progress(event_type, payload):
    if event_type == "stage_start":
        print(f"\n=== STAGE: {payload['stage']} ===\n")
    elif event_type == "stage1":
        print(f"--- {AGENT_DISPLAY_NAMES[payload['agent']]} ---\n{payload['text']}\n")
    elif event_type == "debate_turn":
        print(f"[{payload['turn']}] {AGENT_DISPLAY_NAMES[payload['agent']]}: {payload['text']}\n")
    elif event_type == "cio":
        print(payload["text"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("ticker")
    parser.add_argument("--market", choices=["US", "India"], default=None)
    args = parser.parse_args()

    data = fetch_and_format(args.ticker, market=args.market)
    print("=== FETCHED DATA ===\n")
    print(data)
    print()

    run_committee(args.ticker.upper(), data, on_update=print_progress)
