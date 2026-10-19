"""Volumenprofil: POC és értékterület (VAH/VAL)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .alap import Eredmeny, Kontextus, Forras, Szint, ar, wiki

SAVOK = 48


def szamol(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    if not ktx.van_volumen:
        return Eredmeny("volumenprofil", "Volumenprofil",
                        "Ehhez az eszközhöz nincs megbízható volumenadat (pl. deviza), "
                        "ezért a volumenprofil nem alkalmazható.", alkalmazhato=False, suly=0)
    minta = df.iloc[-min(len(df), 300):]
    tipikus = ((minta["High"] + minta["Low"] + minta["Close"]) / 3).values
    hatarok = np.linspace(minta["Low"].min(), minta["High"].max(), SAVOK + 1)
    vol, _ = np.histogram(tipikus, bins=hatarok, weights=minta["Volume"].values)
    kozepek = (hatarok[:-1] + hatarok[1:]) / 2

    poc_i = int(vol.argmax())
    # értékterület: a POC-tól kiterjesztve, amíg a volumen 70%-át lefedi
    lo, hi, ossz = poc_i, poc_i, vol[poc_i]
    while ossz < 0.7 * vol.sum():
        bal = vol[lo - 1] if lo > 0 else -1
        jobb = vol[hi + 1] if hi < SAVOK - 1 else -1
        if jobb >= bal:
            hi += 1
            ossz += jobb
        else:
            lo -= 1
            ossz += bal
    poc, vah, val = float(kozepek[poc_i]), float(hatarok[hi + 1]), float(hatarok[lo])
    utolso = float(minta["Close"].iloc[-1])

    def tipus(x: float) -> str:
        return "tamasz" if x < utolso else "ellenallas"

    szintek = [
        Szint(poc, tipus(poc), "POC", 0.9,
              f"Point of Control: itt cserélt gazdát a legtöbb volumen az utolsó {len(minta)} "
              "gyertyában – erős mágnes és fordulási zóna."),
        Szint(vah, tipus(vah), "VAH", 0.6, "Az értékterület (volumen 70%-a) felső széle."),
        Szint(val, tipus(val), "VAL", 0.6, "Az értékterület (volumen 70%-a) alsó széle."),
    ]
    if utolso > vah:
        helyzet, irany = "az értékterület felett (vevői elfogadás)", 0.4
    elif utolso < val:
        helyzet, irany = "az értékterület alatt (eladói elfogadás)", -0.4
    else:
        helyzet, irany = "az értékterületen belül (egyensúly, oldalazásra hajlamos)", 0.0
    osszegzes = f"POC {ar(poc)}, VAH {ar(vah)}, VAL {ar(val)}; az ár {helyzet}."
    return Eredmeny("volumenprofil", "Volumenprofil", osszegzes,
                    [osszegzes] + [f"{s.cimke}: {s.indoklas}" for s in szintek],
                    szintek, irany=irany, suly=0.7,
                    forrasok=[wiki("Market profile", "Market_profile"),
                              Forras("Volume Profile (Investopedia)",
                                     "https://www.investopedia.com/terms/v/volume-analysis.asp")])
