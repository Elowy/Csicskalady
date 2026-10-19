"""Gyertyaalakzatok, trendcsatorna és alakzatok (háromszögek), Elliott-hullám."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .alap import (Eredmeny, Kontextus, Sorozat, Szint, ar, atr, datum, fraktal_ablak,
                   fraktal_csucsok, wiki)


def gyertyaalakzatok(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    o, h, l, c = (df[k].values for k in ("Open", "High", "Low", "Close"))
    a = float(atr(df).iloc[-1])
    talalatok: list[tuple[str, str, float]] = []

    for i in range(len(df) - 3, len(df)):
        test = abs(c[i] - o[i])
        felso_kanoc = h[i] - max(c[i], o[i])
        also_kanoc = min(c[i], o[i]) - l[i]
        t = datum(df.index[i])
        if i >= 1:
            ptest = abs(c[i - 1] - o[i - 1])
            if c[i] > o[i] and c[i - 1] < o[i - 1] and c[i] >= o[i - 1] and o[i] <= c[i - 1] and test > ptest:
                talalatok.append(("Bikás bekebelezés", t, 0.5))
            if c[i] < o[i] and c[i - 1] > o[i - 1] and c[i] <= o[i - 1] and o[i] >= c[i - 1] and test > ptest:
                talalatok.append(("Medvés bekebelezés", t, -0.5))
        if test > 0 and also_kanoc > 2 * test and felso_kanoc < test and test < a:
            talalatok.append(("Kalapács / akasztott ember (hosszú alsó kanóc)", t, 0.3))
        if test > 0 and felso_kanoc > 2 * test and also_kanoc < test and test < a:
            talalatok.append(("Hullócsillag / fordított kalapács (hosszú felső kanóc)", t, -0.3))
        if test < 0.1 * (h[i] - l[i]) and h[i] > l[i]:
            talalatok.append(("Doji (bizonytalanság)", t, 0.0))

    if not talalatok:
        return Eredmeny("gyertyaalakzat", "Gyertyaalakzatok",
                        "Az utolsó 3 gyertyában nincs jellegzetes alakzat.", irany=0, suly=0.3,
                        forrasok=[wiki("Candlestick pattern", "Candlestick_pattern")])
    indoklasok = [f"{nev} – {t}" for nev, t, _ in talalatok]
    irany = float(np.clip(sum(x for *_, x in talalatok), -1, 1))
    return Eredmeny("gyertyaalakzat", "Gyertyaalakzatok", "; ".join(indoklasok[-2:]) + ".",
                    indoklasok + ["A gyertyaalakzatok önmagukban gyenge jelzések; szint közelében "
                                  "érvényesek leginkább."],
                    irany=irany, suly=0.3,
                    forrasok=[wiki("Candlestick pattern", "Candlestick_pattern")])


def trendcsatorna(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    n = int(min(len(df), max(60, ktx.horizont_gyertya * 2), 250))
    minta = df.iloc[-n:]
    y = np.log(minta["Close"].values)
    x = np.arange(n)
    meredek, metszet = np.polyfit(x, y, 1)
    illesztett = metszet + meredek * x
    maradek = y - illesztett
    sz = maradek.std()
    r2 = 1 - (maradek ** 2).sum() / ((y - y.mean()) ** 2).sum()
    helyzet = maradek[-1] / sz if sz > 0 else 0.0
    valtozas = (np.exp(meredek * ktx.horizont_gyertya) - 1) * 100

    ido = list(minta.index)
    kozep, felso, also = np.exp(illesztett), np.exp(illesztett + 2 * sz), np.exp(illesztett - 2 * sz)
    indoklasok = [
        f"Log-lineáris regresszió az utolsó {n} gyertyára: gyertyánként {meredek * 100:+.3f}%, "
        f"R² = {r2:.2f} ({'tiszta' if r2 > 0.6 else 'gyenge'} trend).",
        f"Ha a trend változatlanul folytatódna, a horizont végére {valtozas:+.1f}% változást jelentene.",
        f"Az ár a csatorna közepétől {helyzet:+.1f} szórásra van "
        f"({'felső' if helyzet > 1 else ('alsó' if helyzet < -1 else 'középső')} harmad).",
    ]
    irany = float(np.clip(np.sign(meredek) * r2 - 0.2 * helyzet, -1, 1))
    return Eredmeny(
        "trendcsatorna", "Trendcsatorna", indoklasok[0], indoklasok,
        szintek=[Szint(float(felso[-1]), "ellenallas", "Csatorna felső", 0.5, indoklasok[0]),
                 Szint(float(also[-1]), "tamasz", "Csatorna alsó", 0.5, indoklasok[0])],
        sorozatok=[Sorozat("Csatorna közép", ido, list(kozep), szin="#bcbd22", szaggatott=True),
                   Sorozat("Csatorna felső", ido, list(felso), szin="#bcbd22"),
                   Sorozat("Csatorna alsó", ido, list(also), szin="#bcbd22")],
        irany=irany, suly=1.0,
        forrasok=[wiki("Linear regression", "Linear_regression"),
                  wiki("Trend line (technical analysis)", "Trend_line_(technical_analysis)")],
    )


def alakzatok(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    minta = df.iloc[-min(len(df), 150):]
    k = fraktal_ablak(len(minta) * 2)
    csucsok, melyek = fraktal_csucsok(minta, k)
    forrasok = [wiki("Chart pattern", "Chart_pattern"),
                wiki("Triangle (chart pattern)", "Triangle_(chart_pattern)")]
    if len(csucsok) < 3 or len(melyek) < 3:
        return Eredmeny("alakzat", "Alakzatok (háromszög, ék)", "Kevés fordulópont, nincs alakzat.",
                        irany=0, suly=0.7, forrasok=forrasok)
    cs, me = csucsok.iloc[-4:], melyek.iloc[-4:]
    pozicio = {t: i for i, t in enumerate(minta.index)}
    xh = np.array([pozicio[t] for t in cs.index]); xl = np.array([pozicio[t] for t in me.index])
    mh = np.polyfit(xh, cs.values, 1)[0]; ml = np.polyfit(xl, me.values, 1)[0]
    a = float(atr(minta).iloc[-1])
    lapos = a * 0.05  # gyertyánkénti meredekség, ami alatt „vízszintesnek” tekintjük

    if abs(mh) < lapos and ml > lapos:
        nev, irany, magy = "Emelkedő háromszög", 0.5, "vízszintes ellenállás, emelkedő mélypontok"
    elif mh < -lapos and abs(ml) < lapos:
        nev, irany, magy = "Eső háromszög", -0.5, "vízszintes támasz, csökkenő csúcsok"
    elif mh < -lapos and ml > lapos:
        nev, irany, magy = "Szimmetrikus háromszög", 0.0, "csökkenő csúcsok és emelkedő mélypontok"
    elif mh > lapos and ml > lapos and ml > mh:
        nev, irany, magy = "Emelkedő ék", -0.4, "emelkedő, összetartó határvonalak"
    elif mh < -lapos and ml < -lapos and mh < ml:
        nev, irany, magy = "Eső ék", 0.4, "eső, összetartó határvonalak"
    elif abs(mh) < lapos and abs(ml) < lapos:
        nev, irany, magy = "Téglalap / tartomány", 0.0, "vízszintes csúcsok és mélypontok"
    else:
        return Eredmeny("alakzat", "Alakzatok (háromszög, ék)",
                        "A csúcsok és mélypontok nem rajzolnak ki klasszikus alakzatot.",
                        irany=0, suly=0.7, forrasok=forrasok)

    indoklas = (f"{nev}: {magy}. Felső vonal pontjai: "
                + ", ".join(f"{datum(t)} ({ar(p)})" for t, p in cs.items())
                + "; alsó vonal pontjai: "
                + ", ".join(f"{datum(t)} ({ar(p)})" for t, p in me.items()) + ".")
    ido = [minta.index[int(xh[0])], minta.index[-1]]
    fh = np.polyfit(xh, cs.values, 1); fl = np.polyfit(xl, me.values, 1)
    utolso_x = len(minta) - 1
    return Eredmeny(
        "alakzat", "Alakzatok (háromszög, ék)", f"{nev} rajzolódik ki ({magy}).", [indoklas],
        szintek=[Szint(float(np.polyval(fh, utolso_x)), "ellenallas", f"{nev} felső", 0.6, indoklas),
                 Szint(float(np.polyval(fl, utolso_x)), "tamasz", f"{nev} alsó", 0.6, indoklas)],
        sorozatok=[Sorozat(f"{nev} felső", ido, [float(np.polyval(fh, xh[0])), float(np.polyval(fh, utolso_x))], szin="#e377c2"),
                   Sorozat(f"{nev} alsó", [minta.index[int(xl[0])], minta.index[-1]],
                           [float(np.polyval(fl, xl[0])), float(np.polyval(fl, utolso_x))], szin="#e377c2")],
        irany=irany, suly=0.7, forrasok=forrasok,
    )


def elliott(df: pd.DataFrame, ktx: Kontextus) -> Eredmeny:
    # Az Elliott-hullámszámlálás szubjektív; a számítás helyett az AI-elemző kapja
    # feladatul (fraktál-fordulópontokkal segítve), itt csak előkészítjük.
    csucsok, melyek = fraktal_csucsok(df.iloc[-200:], fraktal_ablak(400))
    pontok = sorted([(t, float(p), "csúcs") for t, p in csucsok.items()]
                    + [(t, float(p), "mélypont") for t, p in melyek.items()])[-12:]
    lista = "; ".join(f"{datum(t)} {tip} {ar(p)}" for t, p, tip in pontok)
    return Eredmeny("elliott", "Elliott-hullám (AI)",
                    "Az Elliott-számlálást az AI-elemző végzi az alábbi fordulópontokból.",
                    [f"Fordulópontok: {lista}",
                     "Az Elliott-hullámelmélet értelmezése szubjektív; csak kiegészítő jelzés."],
                    irany=0, suly=0,
                    forrasok=[wiki("Elliott wave principle", "Elliott_wave_principle")])
