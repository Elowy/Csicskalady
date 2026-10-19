"""Fibonacci-visszatérési szintek az utolsó meghatározó kilengésre."""

from __future__ import annotations

import pandas as pd

from .alap import Eredmeny, Kontextus, Sorozat, Szint, ar, datum, wiki

ARANYOK = [0.236, 0.382, 0.5, 0.618, 0.786]


def szamol(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    minta = df.iloc[-min(len(df), 250):]
    t_max, t_min = minta["High"].idxmax(), minta["Low"].idxmin()
    csucs, melypont = float(minta["High"].max()), float(minta["Low"].min())
    utolso = float(minta["Close"].iloc[-1])
    emelkedo = t_min < t_max  # a kilengés mélypontból csúcsba tartott
    tav = csucs - melypont

    szintek = []
    for a in ARANYOK:
        szint = csucs - a * tav if emelkedo else melypont + a * tav
        tipus = "tamasz" if szint < utolso else "ellenallas"
        szintek.append(Szint(
            szint, tipus, f"Fib {a * 100:.1f}%", 0.8 if a in (0.5, 0.618) else 0.5,
            f"A {datum(t_min)} mélypont ({ar(melypont)}) és a {datum(t_max)} csúcs "
            f"({ar(csucs)}) közötti {'emelkedés' if emelkedo else 'esés'} {a * 100:.1f}%-os "
            "visszatérése.",
        ))

    visszateres = (csucs - utolso) / tav if emelkedo else (utolso - melypont) / tav
    if emelkedo:
        irany = 0.4 if visszateres < 0.382 else (0.1 if visszateres < 0.618 else -0.3)
    else:
        irany = -0.4 if visszateres < 0.382 else (-0.1 if visszateres < 0.618 else 0.3)

    osszegzes = (f"Az utolsó {len(minta)} gyertya fő kilengése "
                 f"{'emelkedő' if emelkedo else 'eső'} ({ar(melypont)} → {ar(csucs)}); "
                 f"az ár ennek {visszateres * 100:.0f}%-át adta vissza.")
    indoklasok = [
        osszegzes,
        "A 38,2–61,8% közötti „aranyzóna” a trendfolytatás tipikus belépési területe; "
        "78,6% alatt a kilengés érvénytelenné válhat.",
    ] + [f"{s.cimke}: {ar(s.ar)}" for s in szintek]

    sorozatok = [Sorozat("Fib kilengés", [t_min, t_max] if emelkedo else [t_max, t_min],
                         [melypont, csucs] if emelkedo else [csucs, melypont],
                         szin="#9467bd", szaggatott=True)]
    return Eredmeny("fibonacci", "Fibonacci-visszatérés", osszegzes, indoklasok, szintek,
                    sorozatok, irany=irany, suly=0.5,
                    forrasok=[wiki("Fibonacci retracement", "Fibonacci_retracement")])
