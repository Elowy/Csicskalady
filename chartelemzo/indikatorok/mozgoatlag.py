"""Mozgóátlagok (EMA20, SMA50, SMA200) mint trendszűrők és dinamikus szintek."""

from __future__ import annotations

import pandas as pd

from .alap import Eredmeny, Kontextus, Sorozat, Szint, ar, datum, wiki

ATLAGOK = [("EMA20", 20, True, "#ff7f0e"), ("SMA50", 50, False, "#1f77b4"),
           ("SMA200", 200, False, "#d62728")]


def szamol(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    zaro = df["Close"]
    utolso = float(zaro.iloc[-1])
    sorozatok, szintek, indoklasok = [], [], []
    ertekek: dict[str, pd.Series] = {}
    pont = 0.0

    for nev, n, exp, szin in ATLAGOK:
        if len(zaro) < n + 5:
            indoklasok.append(f"{nev}: nincs elég adat ({len(zaro)} gyertya).")
            continue
        s = zaro.ewm(span=n, adjust=False).mean() if exp else zaro.rolling(n).mean()
        ertekek[nev] = s
        ertek = float(s.iloc[-1])
        meredek = (ertek / float(s.iloc[-6]) - 1) * 100
        felette = utolso > ertek
        pont += (1 if felette else -1) + (0.5 if meredek > 0 else -0.5)
        indoklasok.append(
            f"{nev} = {ar(ertek)}: az ár {'felette' if felette else 'alatta'} van "
            f"({(utolso / ertek - 1) * 100:+.2f}%), az átlag az utolsó 5 gyertyán "
            f"{meredek:+.2f}%-ot {'emelkedett' if meredek > 0 else 'süllyedt'}."
        )
        szintek.append(Szint(ertek, "tamasz" if felette else "ellenallas", nev,
                             0.4 if n == 20 else (0.6 if n == 50 else 0.8),
                             f"Dinamikus {'támasz' if felette else 'ellenállás'}: {indoklasok[-1]}"))
        visszafele = s.iloc[-300:]
        sorozatok.append(Sorozat(nev, list(visszafele.index), list(visszafele.values), szin=szin))

    if "SMA50" in ertekek and "SMA200" in ertekek:
        kul = (ertekek["SMA50"] - ertekek["SMA200"]).dropna()
        valt = kul[(kul > 0) != (kul.shift(1) > 0)].iloc[1:]
        if len(valt):
            t = valt.index[-1]
            arany = "aranykereszt (golden cross)" if kul.iloc[-1] > 0 else "halálkereszt (death cross)"
            indoklasok.append(f"Utolsó SMA50/SMA200 keresztezés: {arany}, {datum(t)}.")

    irany = max(-1.0, min(1.0, pont / (1.5 * max(1, len(ertekek)))))
    trend = "emelkedő" if irany > 0.3 else ("eső" if irany < -0.3 else "vegyes")
    osszegzes = f"Mozgóátlag-trend: {trend} ({len(ertekek)} átlag alapján)."
    return Eredmeny("mozgoatlag", "Mozgóátlagok", osszegzes, indoklasok, szintek, sorozatok,
                    irany=irany, suly=1.5,
                    forrasok=[wiki("Moving average", "Moving_average"),
                              wiki("Golden cross", "Golden_cross")])
