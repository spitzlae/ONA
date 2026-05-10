"""
Portfolio-Analyse mit Yahoo Finance
Für Google Colab: Copy & Paste in eine Zelle

Installiert yfinance, lädt historische Kurse,
verifiziert Einstandskurse, berechnet Performance vs. DAX.
"""

# === CELL 1: Setup & Ticker-Definitionen ===

# !pip install yfinance -q

import yfinance as yf
import pandas as pd
import json
from datetime import datetime

# Portfolio-Positionen mit Yahoo-Tickern
PORTFOLIO = {
    "Airbus SE": {
        "ticker": "AIR.DE",
        "stueck": 104,
        "kaufkurs": 24.04,
        "kaufjahr": 2001,
        "typ": "Aktie",
    },
    "Deutsche Telekom": {
        "ticker": "DTE.DE",
        "stueck": 160,  # 60 + 100
        "kaufkurs": 42.43,  # Durchschnitt
        "kaufjahr": 2001,
        "typ": "Aktie",
    },
    "iShares STOXX Europe 600": {
        "ticker": "EXSA.DE",
        "stueck": 110,
        "kaufkurs": 48.88,
        "kaufjahr": 2001,
        "typ": "ETF",
    },
    "UniESG Aktien Deutschland": {
        "ticker": "0P00000OXR.F",
        "stueck": 100.11,
        "kaufkurs": 45.57,
        "kaufjahr": 2003,
        "typ": "Fonds",
    },
    "UniESG Aktien Europa": {
        "ticker": "0P00000BQC.F",
        "stueck": 109.725,
        "kaufkurs": 39.44,
        "kaufjahr": 2003,
        "typ": "Fonds",
    },
    "UniEuroAktien": {
        "ticker": "0P00000OXK.F",
        "stueck": 99.199,
        "kaufkurs": 39.44,
        "kaufjahr": 2003,
        "typ": "Fonds",
    },
    "UniSector BasicIndustries": {
        "ticker": "0P00000BQ7.F",
        "stueck": 41.05,
        "kaufkurs": 66.77,
        "kaufjahr": 2003,
        "typ": "Fonds",
    },
    "UniSector HighTech": {
        "ticker": "0P00000BQ4.F",
        "stueck": 49.021,
        "kaufkurs": 28.97,
        "kaufjahr": 2003,
        "typ": "Fonds",
    },
    "HSBC MSCI World": {
        "ticker": "H4ZJ.DE",
        "stueck": 400,
        "kaufkurs": 26.06,
        "kaufjahr": 2024,
        "typ": "ETF",
    },
    "Invesco MSCI World": {
        "ticker": "SC0J.DE",
        "stueck": 150,
        "kaufkurs": 78.78,
        "kaufjahr": 2023,
        "typ": "ETF",
    },
    "Bayer AG": {
        "ticker": "BAYN.DE",
        "stueck": 344,
        "kaufkurs": 27.82,
        "kaufjahr": 2024,
        "typ": "Aktie",
    },
    "Berkshire Hathaway": {
        "ticker": "BRK-B",
        "stueck": 25,
        "kaufkurs": 386.60,
        "kaufjahr": 2024,
        "typ": "Aktie",
        "waehrung": "USD",
    },
    "Deutsche Lufthansa": {
        "ticker": "LHA.DE",
        "stueck": 625,
        "kaufkurs": 7.52,
        "kaufjahr": 2024,
        "typ": "Aktie",
    },
    "Flossbach von Storch": {
        "ticker": "0P0000KAJE.F",

        "stueck": 33,
        "kaufkurs": 306.11,
        "kaufjahr": 2024,
        "typ": "Fonds",
    },
    "iShares MSCI EM": {
        "ticker": "IQQE.DE",
        "stueck": 61,
        "kaufkurs": 81.82,
        "kaufjahr": 2024,
        "typ": "ETF",
    },
    "Xtrackers AI": {
        "ticker": "XAIX.DE",
        "stueck": 45,
        "kaufkurs": 111.04,
        "kaufjahr": 2024,
        "typ": "ETF",
    },
}


DAX_TICKER = "^GDAXI"


