"""Aktuális árfolyamadatok letöltése (Yahoo Finance) és a jövőbeli időtengely."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .idosikok import Idosik

FORRAS_NEV = "Yahoo Finance (yfinance)"


@dataclass
class Arfolyam:
    ticker: str
    idosik: Idosik
    df: pd.DataFrame          # Open, High, Low, Close, Volume oszlopok, időindex
    letoltve: datetime

    @property
    def forras_url(self) -> str:
        return f"https://finance.yahoo.com/quote/{self.ticker}"

    @property
    def van_volumen(self) -> bool:
        return bool((self.df["Volume"] > 0).mean() > 0.8)


def letolt(ticker: str, idosik: Idosik) -> Arfolyam:
    import yfinance as yf

    nyers = yf.download(ticker, period=idosik.yf_period, interval=idosik.yf_interval,
                        auto_adjust=False, progress=False, threads=False)
    if nyers is None or nyers.empty:
        raise RuntimeError(f"Nem jött adat a(z) {ticker} tickerre ({idosik.nev}). "
                           "Ellenőrizd a szimbólumot (--szimbolum).")
    if isinstance(nyers.columns, pd.MultiIndex):
        nyers.columns = nyers.columns.get_level_values(0)
    df = nyers[["Open", "High", "Low", "Close", "Volume"]].astype(float).dropna(subset=["Close"])
    if idosik.resample:
        df = atmintaz(df, idosik.resample)
    return Arfolyam(ticker, idosik, df, datetime.now(timezone.utc))


def atmintaz(df: pd.DataFrame, szabaly: str) -> pd.DataFrame:
    out = df.resample(szabaly).agg(
        {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    )
    return out.dropna(subset=["Close"])


def jovobeli_index(df: pd.DataFrame, idosik: Idosik) -> pd.DatetimeIndex:
    """A horizontnak megfelelő jövőbeli gyertya-időpontok.

    A múltban megfigyelt kereskedési idősávokból (hét napja + napszak)
    lépked előre, így a hétvégék és a zárt órák kimaradnak, a 0-24 órás
    piacoknál (kripto) pedig nem.
    """
    utolso = df.index[-1]
    lepes = pd.Timedelta(idosik.gyertya)

    if idosik.kulcs == "1w":
        n = int(round(idosik.horizont / idosik.gyertya))
        return pd.DatetimeIndex([utolso + lepes * (i + 1) for i in range(n)])

    minta = df.index[-min(len(df), 2000):]
    if idosik.kulcs == "1d":
        savok = {t.weekday() for t in minta}
        ervenyes = lambda t: t.weekday() in savok  # noqa: E731
    else:
        savok = {(t.weekday(), t.hour, t.minute) for t in minta}
        ervenyes = lambda t: (t.weekday(), t.hour, t.minute) in savok  # noqa: E731

    if idosik.aktiv_ido:
        if idosik.horizont >= pd.Timedelta(days=1):
            # "következő kereskedési nap": egy átlagos aktív nap gyertyaszáma
            n = int(np.median(pd.Series(1, index=minta).groupby(minta.date).sum()))
        else:
            n = int(round(idosik.horizont / idosik.gyertya))
        hatar = None
    else:
        n = None
        hatar = utolso + pd.Timedelta(idosik.horizont)

    idok: list[pd.Timestamp] = []
    t = utolso
    for _ in range(200_000):
        t = t + lepes
        if hatar is not None and t > hatar:
            break
        if ervenyes(t):
            idok.append(t)
            if n is not None and len(idok) >= n:
                break
    return pd.DatetimeIndex(idok)
