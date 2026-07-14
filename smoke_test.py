"""
Priority 1 smoke test: run the full 9-agent + debate + CIO pipeline against
hand-pasted real AAPL financials (FY2025 10-K figures, in millions USD unless
noted) to judge prompt quality before wiring in live EDGAR/Screener data.

Usage: python smoke_test.py
"""

import sys

from agents.prompts import AGENT_DISPLAY_NAMES
from agents.runner import run_committee

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

AAPL_DATA = """
Company: Apple Inc. (AAPL), US listed, Consumer Electronics / Services
Market cap: ~$3.4T | Share price: ~$225

Income statement (FY2025, USD millions):
- Revenue: 416,000 (prior year 391,000, +6.4% YoY)
- Gross profit: 190,900 (gross margin 45.9%, up from 46.2% prior year)
- Operating income: 130,500 (operating margin 31.4%)
- Net income: 103,200 (net margin 24.8%)
- R&D spend: 34,600 (8.3% of revenue)
- Diluted EPS: 6.71 (prior year 6.11, +9.8%)

Balance sheet:
- Total assets: 365,000
- Total equity: 62,000 (very low relative to assets due to years of buybacks)
- Total debt: 105,000
- Cash & marketable securities: 162,000
- Net cash position (cash - debt): +57,000

Cash flow:
- Operating cash flow: 122,000
- Capex: 11,500
- Free cash flow: 110,500
- Dividends paid: 15,800
- Share buybacks: 90,000 (shares outstanding down ~2.8% YoY)

10-year trend context:
- Revenue CAGR (10yr): ~8%
- Gross margin has expanded from ~38% (2015) to ~46% (2025), driven by Services mix shift
- Services revenue now ~26% of total revenue, growing ~13% YoY, ~70% gross margin
- iPhone still ~50% of revenue, growing low-single-digits
- Buyback program has retired ~40% of shares outstanding over the past decade
- ROIC (approx): ~55-60%, among the highest of any large-cap company

Valuation:
- P/E: ~33.5x (10yr average P/E: ~22x)
- FCF yield: ~3.2%
- EV/EBITDA: ~24x

Qualitative:
- Management: Tim Cook (CEO since 2011), capital return-focused, consistent buyback/dividend policy
- Competitive position: dominant premium smartphone ecosystem, high switching costs, expanding services attach
- Key risks flagged by sell-side: China revenue growth flat to declining (~17% of revenue),
  regulatory pressure on App Store take-rate (EU DMA, US antitrust), AI product roadmap seen as
  behind competitors on generative AI features as of this data
- Insider/institutional: no unusual promoter/insider selling pattern; institutional ownership ~62%
"""

if __name__ == "__main__":
    run_committee("AAPL", AAPL_DATA, on_update=print_progress)
