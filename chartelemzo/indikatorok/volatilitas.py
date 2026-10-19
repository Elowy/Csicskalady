"""Volatilitás-alapú eszközök: Bollinger-szalag és ATR."""

from __future__ import annotations

import pandas as pd

from .alap import Eredmeny, Kontextus, Sorozat, Szint, ar, atr, wiki


def bollinger(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    zaro = df["Close"]
    kozep = zaro.rolling(20).mean()
    szoras = zaro.rolling(20).std()
    felso, also = kozep + 2 * szoras, kozep - 2 * szoras
    szelesseg = (felso - also) / kozep
    utolso = float(zaro.iloc[-1])
    pb = (utolso - also.iloc[-1]) / (felso.iloc[-1] - also.iloc[-1])
    percentilis = float((szelesseg.iloc[-250:] < szelesseg.iloc[-1]).mean() * 100)

    indoklasok = [
        f"Bollinger(20,2): felső {ar(felso.iloc[-1])}, közép {ar(kozep.iloc[-1])}, "
        f"alsó {ar(also.iloc[-1])}; %B = {pb:.2f}.",
        f"A szalag szélessége az utolsó 250 gyertya {percentilis:.0f}. percentilisén van.",
    ]
    if percentilis < 20:
        indoklasok.append("Összeszűkült szalag („squeeze”): alacsony volatilitás, ami gyakran "
                          "nagyobb kitörés előtt jelentkezik – iránya nem következik belőle.")
    elif percentilis > 80:
        indoklasok.append("Kitágult szalag: magas volatilitás, a mozgás kifulladhat.")
    irany = -0.3 if pb > 1 else (0.3 if pb < 0 else (pb - 0.5) * 0.4)

    vissza = slice(-300, None)
    return Eredmeny(
        "bollinger", "Bollinger-szalag", " ".join(indoklasok[1:]), indoklasok,
        szintek=[Szint(float(felso.iloc[-1]), "ellenallas", "BB felső", 0.4,
                       "A 20 periódusos átlag +2 szórás; statisztikai túlnyúlás felett."),
                 Szint(float(also.iloc[-1]), "tamasz", "BB alsó", 0.4,
                       "A 20 periódusos átlag −2 szórás; statisztikai túlnyúlás alatt.")],
        sorozatok=[Sorozat("BB felső", list(felso.index[vissza]), list(felso.values[vissza]), szin="#17becf", szaggatott=True),
                   Sorozat("BB alsó", list(also.index[vissza]), list(also.values[vissza]), szin="#17becf", szaggatott=True)],
        irany=irany, suly=0.5,
        forrasok=[wiki("Bollinger Bands", "Bollinger_Bands")],
    )


def atr_modul(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    a = atr(df)
    ertek = float(a.iloc[-1])
    utolso = float(df["Close"].iloc[-1])
    atlag = float(a.iloc[-100:].mean())
    indoklasok = [
        f"ATR(14) = {ar(ertek)} ({ertek / utolso * 100:.2f}% az árhoz képest).",
        f"Az utolsó 100 gyertya átlagához ({ar(atlag)}) képest "
        f"{'magasabb' if ertek > atlag else 'alacsonyabb'} a volatilitás "
        f"({(ertek / atlag - 1) * 100:+.0f}%).",
        "Az ATR-t használjuk a szintek tűréséhez, a stop távolságához és a szimuláció "
        "volatilitásának igazításához.",
    ]
    return Eredmeny("atr", "ATR (volatilitás)", indoklasok[1], indoklasok, irany=0.0, suly=0.0,
                    forrasok=[wiki("Average true range", "Average_true_range")])
