"""Interaktív Plotly chart: gyertyák, szintek, szellemgyertyák, kitörési tartomány."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from .elorejelzes import Elorejelzes
from .indikatorok import Eredmeny
from .indikatorok.alap import ar

MULT_GYERTYA = 250
# Alapból látható modulok a charton; a többi a legendára kattintva kapcsolható be.
ALAPBOL_LATHATO = {"szintek", "mozgoatlag", "alakzat", "rsi", "macd"}
# Ezeknél a modul saját vonala (pl. mozgóátlag) már mutatja a szintet, nem húzunk vízszintest.
SAJAT_VONAL = {"mozgoatlag", "bollinger", "trendcsatorna", "alakzat"}
SZINT_SZIN = {"tamasz": "#2ca02c", "ellenallas": "#d62728", "semleges": "#7f7f7f"}


def _x(t) -> str:
    t = pd.Timestamp(t)
    return t.strftime("%Y-%m-%d") if (t.hour, t.minute) == (0, 0) else t.strftime("%Y-%m-%d %H:%M")


def rajzol(df: pd.DataFrame, eredmenyek: list[Eredmeny], eloj: Elorejelzes, cim: str,
           lathato_modulok: set[str] | None = None) -> go.Figure:
    lathato_modulok = ALAPBOL_LATHATO if lathato_modulok is None else lathato_modulok
    mult = df.iloc[-max(120, min(MULT_GYERTYA, 3 * len(eloj.jovo_idok))):]
    xm = [_x(t) for t in mult.index]
    xj = [_x(t) for t in eloj.jovo_idok]
    elso_x, utolso_x, vege_x = xm[0], xm[-1], xj[-1]
    lathato = set(xm)

    panelek = ["ar"]
    if any(s.panel == "rsi" for e in eredmenyek for s in e.sorozatok):
        panelek.append("rsi")
    if any(s.panel == "macd" for e in eredmenyek for s in e.sorozatok):
        panelek.append("macd")
    panelek.append("valoszinuseg")
    magassag = {"ar": 0.6, "rsi": 0.13, "macd": 0.13, "valoszinuseg": 0.14}
    cimek = {"ar": "", "rsi": "RSI", "macd": "MACD", "valoszinuseg": "Kitörés kumulált esélye"}
    fig = make_subplots(rows=len(panelek), cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[magassag[p] for p in panelek],
                        subplot_titles=[cimek[p] for p in panelek])
    sor = {p: i + 1 for i, p in enumerate(panelek)}

    fig.add_trace(go.Candlestick(x=xm, open=mult["Open"], high=mult["High"], low=mult["Low"],
                                 close=mult["Close"], name="Árfolyam", legendgroup="ar"), 1, 1)

    # --- előrejelzési legyező (percentilisek) ---
    p = eloj.percentilisek
    for also, felso, atl, nev in ((5, 95, 0.10, "90%-os sáv"), (25, 75, 0.18, "50%-os sáv")):
        fig.add_trace(go.Scatter(x=xj + xj[::-1], y=p[felso] + p[also][::-1], fill="toself",
                                 fillcolor=f"rgba(100,110,250,{atl})", line=dict(width=0),
                                 name=f"Előrejelzés {nev}", legendgroup="legyezo",
                                 hoverinfo="skip"), 1, 1)
    fig.add_trace(go.Scatter(x=xj, y=p[50], name="Medián pálya", legendgroup="legyezo",
                             line=dict(color="rgba(80,80,200,0.9)", dash="dot")), 1, 1)

    # --- szellemgyertyák ---
    sz = eloj.szellem
    fig.add_trace(go.Candlestick(
        x=xj, open=sz["Open"], high=sz["High"], low=sz["Low"], close=sz["Close"],
        name=f"Szellemgyertyák ({_forgatokonyv_nev(eloj.fo_forgatokonyv)})", legendgroup="szellem",
        increasing=dict(line=dict(color="rgba(0,137,123,0.8)"), fillcolor="rgba(0,137,123,0.35)"),
        decreasing=dict(line=dict(color="rgba(198,40,40,0.8)"), fillcolor="rgba(198,40,40,0.35)"),
        opacity=0.75,
    ), 1, 1)

    # --- köztes tartomány a jövőben, kitörési esélyekkel ---
    t = eloj.tartomany
    fig.add_trace(go.Scatter(
        x=[utolso_x, vege_x, vege_x, utolso_x, utolso_x],
        y=[t.felso, t.felso, t.also, t.also, t.felso], fill="toself",
        fillcolor="rgba(255,193,7,0.13)", line=dict(color="rgba(255,160,0,0.8)", width=1),
        name=f"Köztes tartomány ({ar(t.also)} – {ar(t.felso)})", legendgroup="tartomany",
        hovertext=f"Bent marad: {eloj.p_bent:.0%}", hoverinfo="text"), 1, 1)
    kozep_x = xj[len(xj) // 2]
    for y, szoveg, szin, eltol in (
        (t.felso, f"▲ felfelé kitörés: {eloj.p_fel:.0%}", "#1b7f3b", 16),
        (t.also, f"▼ lefelé kitörés: {eloj.p_le:.0%}", "#b71c1c", -16),
        ((t.felso + t.also) / 2, f"↔ oldalazás: {eloj.p_bent:.0%}", "#8a6d00", 0),
    ):
        fig.add_annotation(x=kozep_x, y=y, text=f"<b>{szoveg}</b>", showarrow=False, yshift=eltol,
                           font=dict(color=szin, size=12), bgcolor="rgba(255,255,255,0.7)",
                           row=1, col=1)

    # --- indikátor-szintek és -sorozatok (legendából ki-/bekapcsolhatók) ---
    for e in eredmenyek:
        if not e.alkalmazhato:
            continue
        lathato_e = True if e.kulcs in lathato_modulok else "legendonly"
        for i, s in enumerate([] if e.kulcs in SAJAT_VONAL else e.szintek):
            fig.add_trace(go.Scatter(
                x=[elso_x, vege_x], y=[s.ar, s.ar], mode="lines+text",
                text=["", f"{s.cimke} {ar(s.ar)}"], textposition="middle right",
                textfont=dict(size=9, color=SZINT_SZIN[s.tipus]), cliponaxis=False,
                line=dict(color=SZINT_SZIN[s.tipus], width=1 + 2 * s.erosseg,
                          dash="solid" if e.kulcs == "szintek" else "dash"),
                opacity=0.35 + 0.5 * s.erosseg, name=e.nev, legendgroup=e.kulcs,
                showlegend=i == 0, visible=lathato_e,
                hovertext=f"{s.cimke} {ar(s.ar)}<br>{_tor(s.indoklas)}", hoverinfo="text"), 1, 1)
        for s in e.sorozatok:
            panel = s.panel if s.panel in sor else "ar"
            pontok = [(_x(t), y) for t, y in zip(s.x, s.y) if _x(t) in lathato]
            if not pontok:
                continue
            x, y = (list(v) for v in zip(*pontok))
            if s.nev == "Hisztogram":
                fig.add_trace(go.Bar(x=x, y=y, name=s.nev, legendgroup=e.kulcs, showlegend=False,
                                     marker_color=s.szin, visible=lathato_e), sor[panel], 1)
                continue
            fig.add_trace(go.Scatter(x=x, y=y, name=s.nev, legendgroup=e.kulcs, visible=lathato_e,
                                     line=dict(color=s.szin, width=1.2,
                                               dash="dash" if s.szaggatott else "solid")),
                          sor[panel], 1)

    # --- belépési tervek ---
    for b in eloj.belepesek:
        if not (b.fo or b.valoszinuseg >= 0.25):
            continue
        szin = "#1b7f3b" if b.irany == "long" else "#b71c1c"
        x0, x1 = xj[0], xj[min(len(xj) - 1, max(3, len(xj) // 4))]
        csoport = f"belepes-{b.nev}"
        for y, nev, dash in ((b.belepo, "belépő", "solid"), (b.stop, "stop", "dot"),
                             (b.cel1, "cél 1", "dash")):
            fig.add_trace(go.Scatter(x=[x0, x1], y=[y, y], mode="lines+text",
                                     line=dict(color=szin if nev != "stop" else "#555", width=2 if b.fo else 1,
                                               dash=dash),
                                     text=[f"{b.nev}: {nev} {ar(y)}" if nev == "belépő" else f"{nev} {ar(y)}", ""],
                                     textposition="top right", textfont=dict(size=9, color=szin),
                                     name=f"{'★ ' if b.fo else ''}{b.nev}", legendgroup=csoport,
                                     showlegend=nev == "belépő", hovertext=_tor(b.indoklas),
                                     hoverinfo="text"), 1, 1)

    # --- "most" jelölő ---
    fig.add_shape(type="line", x0=utolso_x, x1=utolso_x, y0=0, y1=1, yref="paper",
                  line=dict(color="#888", dash="dot", width=1))
    fig.add_annotation(x=utolso_x, y=1, yref="paper", text="most", showarrow=False,
                       yanchor="bottom", font=dict(size=10, color="#666"))

    if "rsi" in sor:
        for szint in (30, 70):
            fig.add_hline(y=szint, line=dict(color="#bbb", dash="dot", width=1), row=sor["rsi"], col=1)

    r = sor["valoszinuseg"]
    fig.add_trace(go.Scatter(x=xj, y=eloj.kumulalt_fel, name="Felfelé kitörés esélye",
                             line=dict(color="#1b7f3b"), legendgroup="tartomany"), r, 1)
    fig.add_trace(go.Scatter(x=xj, y=eloj.kumulalt_le, name="Lefelé kitörés esélye",
                             line=dict(color="#b71c1c"), legendgroup="tartomany"), r, 1)
    fig.update_yaxes(tickformat=".0%", range=[0, 1], row=r, col=1)

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=xm + xj,
                     nticks=12, rangeslider_visible=False)
    fig.update_layout(
        title=cim, height=650 + 160 * (len(panelek) - 1), template="plotly_white",
        legend=dict(orientation="v", x=1.02, y=1, font=dict(size=10),
                    title="Kattints a ki-/bekapcsoláshoz"),
        margin=dict(l=50, r=230, t=70, b=40), hovermode="x unified", dragmode="pan",
    )
    return fig


def _tor(szoveg: str, szelesseg: int = 80) -> str:
    sorok, akt = [], ""
    for szo in szoveg.split():
        if len(akt) + len(szo) > szelesseg:
            sorok.append(akt)
            akt = szo
        else:
            akt = f"{akt} {szo}".strip()
    return "<br>".join(sorok + [akt])


def _forgatokonyv_nev(kod: str) -> str:
    return {"fel": "felfelé kitörés", "le": "lefelé kitörés", "oldalazas": "oldalazás"}[kod]
