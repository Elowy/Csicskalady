"""Lendület-oszcillátorok: RSI és MACD."""

from __future__ import annotations

import pandas as pd

from .alap import Eredmeny, Kontextus, Sorozat, datum, fraktal_ablak, wiki


def rsi_sor(zaro: pd.Series, n: int = 14) -> pd.Series:
    valt = zaro.diff()
    nyer = valt.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    veszt = (-valt.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + nyer / veszt)


def rsi(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    r = rsi_sor(df["Close"])
    ertek = float(r.iloc[-1])
    indoklasok = [f"RSI(14) = {ertek:.1f}."]
    irany = 0.0
    if ertek >= 70:
        indoklasok.append("Túlvett zóna (≥70): rövid távon visszaesés vagy oldalazás valószínűbb, "
                          "erős trendben viszont sokáig itt maradhat.")
        irany = -0.4
    elif ertek <= 30:
        indoklasok.append("Túladott zóna (≤30): pattanás valószínűbb, de eső trendben tartósan "
                          "itt maradhat.")
        irany = 0.4
    else:
        irany = (ertek - 50) / 50 * 0.5
        indoklasok.append(f"Semleges tartomány; 50 {'felett' if ertek > 50 else 'alatt'} a "
                          f"lendület {'vevő' if ertek > 50 else 'eladó'} oldali.")

    div = _divergencia(df, r)
    if div:
        indoklasok.append(div[0])
        irany += div[1]

    vissza = r.iloc[-300:]
    return Eredmeny("rsi", "RSI", indoklasok[0] + " " + indoklasok[1], indoklasok,
                    sorozatok=[Sorozat("RSI(14)", list(vissza.index), list(vissza.values),
                                       panel="rsi", szin="#7f7f7f")],
                    irany=max(-1, min(1, irany)), suly=1.0,
                    forrasok=[wiki("Relative strength index", "Relative_strength_index")])


def _divergencia(df: pd.DataFrame, r: pd.Series) -> tuple[str, float] | None:
    minta = df.iloc[-120:]
    k = fraktal_ablak(len(minta) * 3)
    h, l = minta["High"], minta["Low"]
    csucsok = h[h == h.rolling(2 * k + 1, center=True).max()].dropna()
    melyek = l[l == l.rolling(2 * k + 1, center=True).min()].dropna()
    if len(csucsok) >= 2:
        (t1, p1), (t2, p2) = list(csucsok.items())[-2:]
        if p2 > p1 and r[t2] < r[t1]:
            return (f"Medvés divergencia: az ár magasabb csúcsot ért el ({datum(t2)}), az RSI "
                    "alacsonyabbat – gyengülő emelkedés.", -0.3)
    if len(melyek) >= 2:
        (t1, p1), (t2, p2) = list(melyek.items())[-2:]
        if p2 < p1 and r[t2] > r[t1]:
            return (f"Bikás divergencia: az ár alacsonyabb mélypontot ért el ({datum(t2)}), az "
                    "RSI magasabbat – gyengülő esés.", 0.3)
    return None


def macd(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    zaro = df["Close"]
    m = zaro.ewm(span=12, adjust=False).mean() - zaro.ewm(span=26, adjust=False).mean()
    jel = m.ewm(span=9, adjust=False).mean()
    hiszt = m - jel
    keresztek = hiszt[(hiszt > 0) != (hiszt.shift(1) > 0)].iloc[1:]
    indoklasok = [f"MACD(12,26,9) = {m.iloc[-1]:.4g}, jelvonal = {jel.iloc[-1]:.4g}, "
                  f"hisztogram = {hiszt.iloc[-1]:.4g}."]
    if len(keresztek):
        t = keresztek.index[-1]
        hany = len(df.loc[t:]) - 1
        tipus = "vételi (MACD a jelvonal fölé)" if hiszt.iloc[-1] > 0 else "eladási (MACD a jelvonal alá)"
        indoklasok.append(f"Utolsó keresztezés: {tipus}, {datum(t)} ({hany} gyertyája).")
    novekvo = abs(hiszt.iloc[-1]) > abs(hiszt.iloc[-2])
    indoklasok.append(f"A hisztogram {'erősödik' if novekvo else 'gyengül'}; a MACD a 0 vonal "
                      f"{'felett' if m.iloc[-1] > 0 else 'alatt'} van.")
    irany = (0.5 if hiszt.iloc[-1] > 0 else -0.5) + (0.3 if m.iloc[-1] > 0 else -0.3)
    if not novekvo:
        irany *= 0.5
    vissza = slice(-300, None)
    return Eredmeny("macd", "MACD", " ".join(indoklasok[1:]) or indoklasok[0], indoklasok,
                    sorozatok=[
                        Sorozat("MACD", list(m.index[vissza]), list(m.values[vissza]), "macd", "#1f77b4"),
                        Sorozat("Jelvonal", list(jel.index[vissza]), list(jel.values[vissza]), "macd", "#ff7f0e"),
                        Sorozat("Hisztogram", list(hiszt.index[vissza]), list(hiszt.values[vissza]), "macd", "#8c8c8c"),
                    ],
                    irany=max(-1, min(1, irany)), suly=1.0,
                    forrasok=[wiki("MACD", "MACD")])
