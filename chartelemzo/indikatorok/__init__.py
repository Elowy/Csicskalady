"""Kapcsolható indikátorok nyilvántartása."""

from __future__ import annotations

import pandas as pd

from . import fibonacci, mintazatok, mozgoatlag, oszcillatorok, szintek, volatilitas, volumenprofil
from .alap import Eredmeny, Forras, Indikator, Kontextus, Sorozat, Szint

INDIKATOROK: dict[str, Indikator] = {i.kulcs: i for i in [
    Indikator("szintek", "Támasz / ellenállás", "Fraktál-fordulópontok klaszterezése", szintek.szamol),
    Indikator("fibonacci", "Fibonacci-visszatérés", "Az utolsó fő kilengés szintjei", fibonacci.szamol),
    Indikator("mozgoatlag", "Mozgóátlagok", "EMA20, SMA50, SMA200", mozgoatlag.szamol),
    Indikator("rsi", "RSI", "Relatív erő index + divergencia", oszcillatorok.rsi),
    Indikator("macd", "MACD", "Trendkövető lendület", oszcillatorok.macd),
    Indikator("bollinger", "Bollinger-szalag", "Volatilitási szalag, squeeze", volatilitas.bollinger),
    Indikator("atr", "ATR", "Átlagos valódi tartomány", volatilitas.atr_modul),
    Indikator("volumenprofil", "Volumenprofil", "POC, VAH, VAL", volumenprofil.szamol),
    Indikator("gyertyaalakzat", "Gyertyaalakzatok", "Bekebelezés, kalapács, doji…", mintazatok.gyertyaalakzatok),
    Indikator("trendcsatorna", "Trendcsatorna", "Regressziós csatorna ±2σ", mintazatok.trendcsatorna),
    Indikator("alakzat", "Alakzatok", "Háromszögek, ékek, tartomány", mintazatok.alakzatok),
    Indikator("elliott", "Elliott-hullám (AI)", "AI által értelmezett hullámszámlálás", mintazatok.elliott),
]}


def kivalaszt(alap: list[str], be: list[str] | None = None, ki: list[str] | None = None) -> list[str]:
    valasztott = list(dict.fromkeys(alap + (be or [])))
    valasztott = [k for k in valasztott if k not in set(ki or [])]
    ismeretlen = [k for k in valasztott + (ki or []) if k not in INDIKATOROK]
    if ismeretlen:
        raise ValueError(f"Ismeretlen indikátor: {', '.join(ismeretlen)}. "
                         f"Elérhető: {', '.join(INDIKATOROK)}")
    return valasztott


def futtat(df: pd.DataFrame, ktx: Kontextus, kulcsok: list[str]) -> list[Eredmeny]:
    eredmenyek = []
    for k in kulcsok:
        try:
            eredmenyek.append(INDIKATOROK[k].szamol(df, ktx))
        except Exception as e:  # egy hibás modul ne buktassa el az egész elemzést
            eredmenyek.append(Eredmeny(k, INDIKATOROK[k].nev, f"Hiba a számításban: {e}",
                                       alkalmazhato=False, suly=0))
    return eredmenyek


def konszenzus(eredmenyek: list[Eredmeny]) -> float:
    sulyok = [(e.irany, e.suly) for e in eredmenyek if e.alkalmazhato and e.suly > 0]
    ossz = sum(s for _, s in sulyok)
    return sum(i * s for i, s in sulyok) / ossz if ossz else 0.0


__all__ = ["INDIKATOROK", "Eredmeny", "Forras", "Kontextus", "Sorozat", "Szint",
           "futtat", "kivalaszt", "konszenzus"]
