"""
Data-layer smoke test — no Claude API calls. Fetches and normalizes real
financials for one US ticker (Palantir) and one India ticker (Urban Company)
to validate the EDGAR/Screener fetchers and shared formatting before the
agent pipeline is pointed at live data.

Usage: python test_data_layer.py
"""

from orchestrator.analyze import fetch_and_format

if __name__ == "__main__":
    print("############ PALANTIR (PLTR, US / EDGAR) ############\n")
    print(fetch_and_format("PLTR", market="US"))

    print("\n\n############ URBAN COMPANY (URBANCO, India / Screener) ############\n")
    print(fetch_and_format("URBANCO", market="India"))
