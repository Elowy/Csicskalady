"""Idősíkok (chart-felbontások) és a hozzájuk tartozó előrejelzési horizontok."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta


@dataclass(frozen=True)
class Idosik:
    kulcs: str              # belső azonosító, pl. "1d"
    nev: str                # magyar megnevezés
    yf_interval: str        # yfinance letöltési felbontás
    yf_period: str          # mennyi előzményt töltünk le
    resample: str | None    # ha a yfinance nem adja közvetlenül (pl. 4h)
    gyertya: timedelta      # egy gyertya hossza
    horizont: timedelta     # előrejelzési horizont
    horizont_nev: str
    # True: a horizont aktív kereskedési időben értendő (pl. "8 óra" = 8 óra
    # nyitott piac), False: naptári időben (pl. "3 hónap").
    aktiv_ido: bool


IDOSIKOK: dict[str, Idosik] = {
    "1w": Idosik("1w", "heti", "1wk", "10y", None, timedelta(weeks=1),
                 timedelta(days=365), "következő 1 év", False),
    "1d": Idosik("1d", "napos", "1d", "5y", None, timedelta(days=1),
                 timedelta(days=91), "következő 3 hónap", False),
    "4h": Idosik("4h", "4 órás", "1h", "730d", "4h", timedelta(hours=4),
                 timedelta(days=30), "következő 1 hónap", False),
    "1h": Idosik("1h", "órás", "1h", "365d", None, timedelta(hours=1),
                 timedelta(days=14), "következő 2 hét", False),
    "15m": Idosik("15m", "negyedórás", "15m", "60d", None, timedelta(minutes=15),
                  timedelta(days=1), "következő kereskedési nap", True),
    "5m": Idosik("5m", "5 perces", "5m", "30d", None, timedelta(minutes=5),
                 timedelta(hours=8), "következő 8 óra", True),
}

# TradingView / szabad szöveges jelölések -> belső kulcs
_ALIASOK = {
    "1w": "1w", "w": "1w", "1wk": "1w", "heti": "1w", "week": "1w", "weekly": "1w",
    "1d": "1d", "d": "1d", "napos": "1d", "day": "1d", "daily": "1d",
    "4h": "4h", "240": "4h", "4 órás": "4h", "4óra": "4h",
    "1h": "1h", "60": "1h", "h": "1h", "órás": "1h", "hourly": "1h",
    "15m": "15m", "15": "15m", "15min": "15m", "negyedórás": "15m",
    "5m": "5m", "5": "5m", "5min": "5m", "5 perces": "5m",
}


def idosik(kulcs: str) -> Idosik:
    k = _ALIASOK.get(kulcs.strip().lower())
    if k is None:
        tamogatott = ", ".join(IDOSIKOK)
        raise ValueError(f"Ismeretlen idősík: {kulcs!r}. Támogatott: {tamogatott}")
    return IDOSIKOK[k]
