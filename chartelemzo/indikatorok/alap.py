"""Az indikátor-modulok közös adatszerkezetei és segédfüggvényei."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Literal

import numpy as np
import pandas as pd

SzintTipus = Literal["tamasz", "ellenallas", "semleges"]
Panel = Literal["ar", "rsi", "macd", "volumen"]


@dataclass
class Forras:
    cim: str
    url: str


@dataclass
class Szint:
    ar: float
    tipus: SzintTipus
    cimke: str
    erosseg: float          # 0..1
    indoklas: str


@dataclass
class Sorozat:
    nev: str
    x: list
    y: list
    panel: Panel = "ar"
    szin: str | None = None
    szaggatott: bool = False


@dataclass
class Eredmeny:
    kulcs: str
    nev: str
    osszegzes: str                       # 1-2 mondatos magyar összefoglaló
    indoklasok: list[str] = field(default_factory=list)
    szintek: list[Szint] = field(default_factory=list)
    sorozatok: list[Sorozat] = field(default_factory=list)
    irany: float = 0.0                   # -1 (eső) .. +1 (emelkedő)
    suly: float = 1.0                    # súly az irány-konszenzusban
    forrasok: list[Forras] = field(default_factory=list)
    alkalmazhato: bool = True            # pl. forexnél nincs volumen

    def json(self, sorozatok_nelkul: bool = True) -> dict:
        d = asdict(self)
        if sorozatok_nelkul:
            d.pop("sorozatok")
        return d


@dataclass
class Indikator:
    kulcs: str
    nev: str
    leiras: str
    szamol: Callable[[pd.DataFrame, "Kontextus"], Eredmeny]
    alapbol_be: bool = True


@dataclass
class Kontextus:
    ticker: str
    idosik_nev: str
    van_volumen: bool
    horizont_gyertya: int


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    elozo = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - elozo).abs(),
                    (df["Low"] - elozo).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def fraktal_csucsok(df: pd.DataFrame, k: int) -> tuple[pd.Series, pd.Series]:
    """Bill Williams-féle fraktálok: helyi csúcs/mélypont, ha k gyertyán belül
    mindkét oldalon az a szélsőérték. Visszaad két (idő -> ár) sorozatot."""
    h, l = df["High"], df["Low"]
    ablak = 2 * k + 1
    csucs = h[(h == h.rolling(ablak, center=True).max())]
    melypont = l[(l == l.rolling(ablak, center=True).min())]
    return csucs.dropna(), melypont.dropna()


def fraktal_ablak(n: int) -> int:
    return int(np.clip(n // 60, 3, 8))


def datum(t) -> str:
    t = pd.Timestamp(t)
    if t.hour == 0 and t.minute == 0:
        return t.strftime("%Y-%m-%d")
    return t.strftime("%Y-%m-%d %H:%M")


def ar(x: float) -> str:
    if x >= 1000:
        return f"{x:,.2f}".replace(",", " ")
    if x >= 10:
        return f"{x:.2f}"
    if x >= 1:
        return f"{x:.5f}"
    return f"{x:.6g}"


def wiki(cim: str, lap: str) -> Forras:
    return Forras(cim, f"https://en.wikipedia.org/wiki/{lap}")
