"""Támasz- és ellenállásszintek fraktál-csúcsok klaszterezéséből."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .alap import Eredmeny, Forras,Kontextus, Szint, ar, atr, datum, fraktal_ablak, fraktal_csucsok, wiki

MAX_SZINT_OLDALANKENT = 4


def szamol(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    minta = df.iloc[-min(len(df), 500):]
    k = fraktal_ablak(len(minta))
    csucsok, melypontok = fraktal_csucsok(minta, k)
    utolso = float(minta["Close"].iloc[-1])
    tures = float(atr(minta).iloc[-1]) * 0.6

    pontok = sorted(
        [(float(p), t, "csúcs") for t, p in csucsok.items()]
        + [(float(p), t, "mélypont") for t, p in melypontok.items()]
    )
    klaszterek: list[list[tuple[float, pd.Timestamp, str]]] = []
    for p in pontok:
        if klaszterek and p[0] - np.mean([q[0] for q in klaszterek[-1]]) <= tures:
            klaszterek[-1].append(p)
        else:
            klaszterek.append([p])

    kezdet, veg = minta.index[0], minta.index[-1]
    jeloltek = []
    for kl in klaszterek:
        szint = float(np.mean([q[0] for q in kl]))
        idok = sorted(q[1] for q in kl)
        # frissesség: 0 (minta eleje) .. 1 (legutóbbi gyertya)
        friss = (idok[-1] - kezdet) / (veg - kezdet) if veg > kezdet else 1.0
        pont = len(kl) + 1.5 * friss
        jeloltek.append((pont, szint, kl, idok))

    if not jeloltek:
        return Eredmeny("szintek", "Támasz / ellenállás", "Nem található elég fordulópont.",
                        alkalmazhato=False)
    max_pont = max(j[0] for j in jeloltek)

    tamaszok, ellenallasok = [], []
    for pont, szint, kl, idok in sorted(jeloltek, key=lambda j: -j[0]):
        tipus = "tamasz" if szint < utolso else "ellenallas"
        cel = tamaszok if tipus == "tamasz" else ellenallasok
        if len(cel) >= MAX_SZINT_OLDALANKENT or len(kl) < 2:
            continue
        csucs_db = sum(1 for q in kl if q[2] == "csúcs")
        melypont_db = len(kl) - csucs_db
        szerep = ""
        if csucs_db and melypont_db:
            szerep = (" A szint szerepcserés: korábban "
                      f"{'ellenállás' if tipus == 'tamasz' else 'támasz'} volt, most "
                      f"{'támasz' if tipus == 'tamasz' else 'ellenállás'}.")
        erintesek = ", ".join(datum(t) for t in idok[-5:])
        indoklas = (f"{len(kl)} fordulópont (k={k} fraktál) ±{ar(tures)} sávon belül "
                    f"({csucs_db} csúcs, {melypont_db} mélypont); utolsó érintések: {erintesek}."
                    f"{szerep}")
        cel.append(Szint(szint, tipus, f"{'T' if tipus == 'tamasz' else 'E'}{len(cel) + 1}",
                         round(pont / max_pont, 2), indoklas))

    tamaszok.sort(key=lambda s: -s.ar)
    ellenallasok.sort(key=lambda s: s.ar)
    for i, s in enumerate(tamaszok):
        s.cimke = f"T{i + 1}"
    for i, s in enumerate(ellenallasok):
        s.cimke = f"E{i + 1}"

    indoklasok = [f"{s.cimke} {ar(s.ar)}: {s.indoklas}" for s in ellenallasok[::-1] + tamaszok]
    kozeli_t = tamaszok[0].ar if tamaszok else None
    kozeli_e = ellenallasok[0].ar if ellenallasok else None
    osszegzes = (f"Legközelebbi támasz: {ar(kozeli_t) if kozeli_t else '–'}, "
                 f"legközelebbi ellenállás: {ar(kozeli_e) if kozeli_e else '–'} "
                 f"(utolsó ár: {ar(utolso)}).")
    irany = 0.0
    if kozeli_t and kozeli_e:
        # ha az ár közelebb van a támaszhoz, enyhén emelkedő (pattanás) várható
        pozicio = (utolso - kozeli_t) / (kozeli_e - kozeli_t)
        irany = float(np.clip(0.5 - pozicio, -0.5, 0.5))

    return Eredmeny(
        "szintek", "Támasz / ellenállás", osszegzes, indoklasok,
        szintek=tamaszok + ellenallasok, irany=irany, suly=0.5,
        forrasok=[wiki("Support and resistance", "Support_and_resistance"),
                  Forras("Fractal Indicator (Investopedia)",
                         "https://www.investopedia.com/terms/f/fractal.asp")],
    )
