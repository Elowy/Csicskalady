"""Önálló HTML-jelentés: chart, valószínűségek, belépők, indoklások, források."""

from __future__ import annotations

from html import escape

import markdown
import plotly.graph_objects as go

from .elorejelzes import Elorejelzes
from .indikatorok import Eredmeny
from .indikatorok.alap import ar

CSS = """
:root { --szoveg:#1d1d1f; --halvany:#6e6e73; --hatter:#fff; --kartya:#f5f5f7; --vonal:#e0e0e5;
        --fel:#1b7f3b; --le:#b71c1c; --oldal:#8a6d00; }
@media (prefers-color-scheme: dark) { :root { --szoveg:#f2f2f7; --halvany:#a1a1a6; --hatter:#111;
        --kartya:#1c1c1e; --vonal:#333; } }
body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; color: var(--szoveg);
       background: var(--hatter); margin: 0 auto; max-width: 1400px; padding: 16px; line-height: 1.5; }
h1 { margin-bottom: 4px; } .al { color: var(--halvany); margin-top: 0; }
.kartyak { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
.kartya { background: var(--kartya); border-radius: 12px; padding: 14px 16px; }
.kartya .szam { font-size: 2rem; font-weight: 700; }
.fel { color: var(--fel); } .le { color: var(--le); } .oldal { color: var(--oldal); }
table { border-collapse: collapse; width: 100%; font-size: .92rem; }
th, td { border-bottom: 1px solid var(--vonal); padding: 6px 8px; text-align: left; vertical-align: top; }
tr.fo { font-weight: 600; background: rgba(255,193,7,.12); }
details { background: var(--kartya); border-radius: 10px; padding: 8px 14px; margin: 8px 0; }
summary { cursor: pointer; font-weight: 600; }
.ki { opacity: .55; } .forras { font-size: .85rem; color: var(--halvany); }
.chart { overflow-x: auto; } img.eredeti { max-width: 100%; border-radius: 8px; border: 1px solid var(--vonal); }
.figyelem { font-size: .85rem; color: var(--halvany); border-top: 1px solid var(--vonal); margin-top: 24px; padding-top: 8px; }
"""


def automatikus_szoveg(eredmenyek: list[Eredmeny], eloj: Elorejelzes, konszenzus: float) -> str:
    """AI nélküli, a számításokból összerakott magyar összefoglaló (Markdown)."""
    irany = "emelkedő" if konszenzus > 0.15 else ("eső" if konszenzus < -0.15 else "semleges")
    sorok = [
        "## Összkép",
        f"Az indikátorok súlyozott konszenzusa **{konszenzus:+.2f}** ({irany}). "
        f"A szimuláció szerint a(z) {ar(eloj.tartomany.also)} – {ar(eloj.tartomany.felso)} "
        f"tartományból **{eloj.p_fel:.0%}** eséllyel felfelé, **{eloj.p_le:.0%}** eséllyel lefelé "
        f"tör ki az ár, **{eloj.p_bent:.0%}** eséllyel a horizont végéig benne marad "
        f"(a horizont végén {eloj.p_vegen['bent']:.0%} eséllyel van a tartományban). "
        f"A mediánpálya a horizont végére {eloj.varhato_valtozas_median:+.1%} változást mutat.",
        "## Indikátorok",
    ]
    for e in eredmenyek:
        if e.alkalmazhato:
            sorok.append(f"- **{e.nev}** (irány {e.irany:+.2f}): {e.osszegzes}")
    return "\n\n".join(sorok)


def html(*, cim: str, alcim: str, fig: go.Figure, eredmenyek: list[Eredmeny], eloj: Elorejelzes,
         konszenzus: float, szoveg_md: str, ai_forrasok: list[dict], adatforras: tuple[str, str],
         otlet: str | None, kep_fajl: str | None, elozmenyek: list[dict], ertekeles: dict | None,
         kikapcsolt: list[str]) -> str:
    r = []
    r.append(f"<h1>{escape(cim)}</h1><p class='al'>{escape(alcim)}</p>")

    t = eloj.tartomany
    r.append("<div class='kartyak'>"
             f"<div class='kartya'><div>Felfelé kitörés</div><div class='szam fel'>{eloj.p_fel:.0%}</div>"
             f"<div>{escape(t.felso_cimke)} {ar(t.felso)} felett</div></div>"
             f"<div class='kartya'><div>Oldalazás</div><div class='szam oldal'>{eloj.p_bent:.0%}</div>"
             f"<div>{ar(t.also)} – {ar(t.felso)} között</div></div>"
             f"<div class='kartya'><div>Lefelé kitörés</div><div class='szam le'>{eloj.p_le:.0%}</div>"
             f"<div>{escape(t.also_cimke)} {ar(t.also)} alatt</div></div>"
             f"<div class='kartya'><div>Indikátor-konszenzus</div><div class='szam'>{konszenzus:+.2f}</div>"
             f"<div>−1 eső … +1 emelkedő</div></div></div>")
    v = eloj.p_vegen
    r.append(f"<p>A kártyák azt mutatják, merre hagyja el <b>először</b> a záróár a tartományt a "
             f"horizonton belül. A horizont <b>végén</b> a záróár várhatóan: felette "
             f"<span class='fel'>{v['fel']:.0%}</span>, bent <span class='oldal'>{v['bent']:.0%}</span>, "
             f"alatta <span class='le'>{v['le']:.0%}</span>.</p><p>{escape(t.indoklas)}</p>")

    r.append("<div class='chart'>" + fig.to_html(full_html=False, include_plotlyjs="cdn",
                                                 config={"scrollZoom": True, "displaylogo": False})
             + "</div>")

    r.append("<h2>Belépési tervek</h2><table><tr><th>Forgatókönyv</th><th>Irány</th><th>Esély</th>"
             "<th>Belépő</th><th>Stop</th><th>1. cél</th><th>2. cél</th><th>Indoklás</th></tr>")
    for b in eloj.belepesek:
        r.append(f"<tr class='{'fo' if b.fo else ''}'><td>{'★ ' if b.fo else ''}{escape(b.nev)}</td>"
                 f"<td>{b.irany}</td><td>{b.valoszinuseg:.0%}</td><td>{ar(b.belepo)}</td>"
                 f"<td>{ar(b.stop)}</td><td>{ar(b.cel1)}</td><td>{ar(b.cel2) if b.cel2 else '–'}</td>"
                 f"<td>{escape(b.indoklas)}</td></tr>")
    r.append("</table>")

    if otlet:
        r.append(f"<h2>Saját elképzelés</h2><blockquote>{escape(otlet)}</blockquote>")
    if ertekeles:
        r.append("<h2>Az előző elemzés kiértékelése</h2><ul>"
                 + "".join(f"<li>{escape(str(s))}</li>" for s in ertekeles.get("megallapitasok", []))
                 + "</ul>")
    if elozmenyek:
        r.append("<details><summary>Előzmények (finomítási lánc)</summary><ul>"
                 + "".join(f"<li>#{e['id']} – {escape(e['letrehozva'])}: {escape(e.get('osszegzes') or '')}</li>"
                           for e in elozmenyek) + "</ul></details>")

    r.append("<h2>Elemzés</h2>" + markdown.markdown(szoveg_md, extensions=["tables"]))
    if ai_forrasok:
        r.append("<h3>Webes források</h3><ul>" + "".join(
            f"<li><a href='{escape(f['url'])}'>{escape(f['cim'] or f['url'])}</a></li>" for f in ai_forrasok)
            + "</ul>")

    r.append("<h2>Indikátorok részletesen</h2>")
    for e in eredmenyek:
        osztaly = "" if e.alkalmazhato else " class='ki'"
        r.append(f"<details{osztaly}><summary>{escape(e.nev)} — {escape(e.osszegzes)}</summary><ul>"
                 + "".join(f"<li>{escape(i)}</li>" for i in e.indoklasok) + "</ul>")
        if e.szintek:
            r.append("<table><tr><th>Szint</th><th>Ár</th><th>Típus</th><th>Erősség</th><th>Miért itt?</th></tr>"
                     + "".join(f"<tr><td>{escape(s.cimke)}</td><td>{ar(s.ar)}</td><td>{s.tipus}</td>"
                               f"<td>{s.erosseg:.2f}</td><td>{escape(s.indoklas)}</td></tr>" for s in e.szintek)
                     + "</table>")
        if e.forrasok:
            r.append("<p class='forras'>Források: " + ", ".join(
                f"<a href='{escape(f.url)}'>{escape(f.cim)}</a>" for f in e.forrasok) + "</p>")
        r.append("</details>")
    if kikapcsolt:
        r.append(f"<p class='forras'>Kikapcsolt modulok: {escape(', '.join(kikapcsolt))}</p>")

    r.append("<h2>Módszertan és adatforrás</h2>"
             f"<p>{escape(eloj.modszer)}</p>"
             f"<p class='forras'>Árfolyamadat: <a href='{escape(adatforras[1])}'>{escape(adatforras[0])}</a>. "
             "Szimuláció: " + ", ".join(f"<a href='{escape(f.url)}'>{escape(f.cim)}</a>" for f in eloj.forrasok)
             + "</p>")
    if kep_fajl:
        r.append(f"<details><summary>Beküldött kép</summary><img class='eredeti' src='{escape(kep_fajl)}' "
                 "alt='Beküldött TradingView képernyőkép'></details>")
    r.append("<p class='figyelem'>Ez egy automatizált technikai elemzés, nem befektetési tanácsadás. "
             "A valószínűségek múltbeli árfolyammozgásokon alapuló szimulációból származnak, és nem "
             "garantálják a jövőbeli eredményt.</p>")

    return ("<!doctype html><html lang='hu'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>{escape(cim)}</title><style>{CSS}</style></head><body>"
            + "\n".join(r) + "</body></html>")
