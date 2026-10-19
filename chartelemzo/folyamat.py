"""A teljes elemzési folyamat: kép -> adat -> indikátorok -> szimuláció -> jelentés -> napló."""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from . import abra, adat, ai, indikatorok, jelentes
from .elorejelzes import szimulal, tartomany_valaszt
from .idosikok import idosik as idosik_keres
from .indikatorok.alap import Kontextus, ar
from .naplo import Bejegyzes, Naplo, adatkonyvtar
from .szimbolum import yahoo_ticker


def beallitasok() -> dict:
    alap = tomllib.loads((Path(__file__).with_name("beallitasok.toml")).read_text("utf-8"))
    helyi = Path("beallitasok.toml")
    if helyi.exists():
        for szekcio, ertekek in tomllib.loads(helyi.read_text("utf-8")).items():
            alap.setdefault(szekcio, {}).update(ertekek)
    return alap


@dataclass
class Keres:
    kep: Path | None = None
    szimbolum: str | None = None
    idosik: str | None = None
    otlet: str | None = None
    be: list[str] = field(default_factory=list)
    ki: list[str] = field(default_factory=list)
    tartomany: tuple[float, float] | None = None
    ai: bool = True
    webes_kereses: bool | None = None
    irany_sulyozas: bool | None = None
    szulo_id: int | None = None


@dataclass
class Kimenet:
    id: int
    jelentes: Path
    osszegzes: str
    figyelmeztetesek: list[str]


def elemez(k: Keres, naplo: Naplo | None = None, naplo_kiir=print) -> Kimenet:
    cfg = beallitasok()
    naplo = naplo or Naplo()
    figy: list[str] = []
    szulo: Bejegyzes | None = naplo.leker(k.szulo_id) if k.szulo_id else None

    # 1. Kép-kiolvasó agent
    kep_adat = None
    if k.kep and k.ai:
        try:
            naplo_kiir("• Kép kiolvasása (Claude)…")
            kep_adat = ai.kep_kiolvas(k.kep)
        except ai.AINemElerheto as e:
            figy.append(str(e))
        except Exception as e:  # a kép kiolvasása nélkül is mehet tovább
            figy.append(f"A kép kiolvasása nem sikerült: {e}")

    szimbolum = k.szimbolum or (kep_adat and kep_adat.szimbolum) or (szulo and szulo.szimbolum)
    idosik_kod = k.idosik or (kep_adat and kep_adat.idosik) or (szulo and szulo.idosik)
    if not szimbolum or not idosik_kod:
        raise ValueError("Nem sikerült megállapítani a szimbólumot és/vagy az idősíkot. "
                         "Add meg: --szimbolum NASDAQ:AAPL --idosik 1d")
    ids = idosik_keres(idosik_kod)
    ticker = yahoo_ticker(szimbolum, kep_adat.eszkozosztaly if kep_adat else None)

    # 2. Aktuális adat
    naplo_kiir(f"• Adatletöltés: {ticker} ({ids.nev})…")
    arf = adat.letolt(ticker, ids)
    df = arf.df
    utolso = float(df["Close"].iloc[-1])
    if kep_adat and kep_adat.utolso_ar and abs(kep_adat.utolso_ar / utolso - 1) > 0.05:
        figy.append(f"A képen látható ár ({ar(kep_adat.utolso_ar)}) több mint 5%-kal eltér a "
                    f"letöltött aktuális ártól ({ar(utolso)}) – régi kép vagy más szimbólum?")

    # 3. Indikátorok
    kulcsok = indikatorok.kivalaszt(cfg["indikatorok"]["alapbol"], k.be, k.ki)
    if not k.ai and "elliott" in kulcsok:
        kulcsok.remove("elliott")
    jovo = adat.jovobeli_index(df, ids)
    ktx = Kontextus(ticker, ids.nev, arf.van_volumen, len(jovo))
    naplo_kiir(f"• {len(kulcsok)} indikátor számítása…")
    eredmenyek = indikatorok.futtat(df, ktx, kulcsok)
    kons = indikatorok.konszenzus(eredmenyek)

    # 4. Kitörési szimuláció
    kezi = k.tartomany
    if kezi is None and kep_adat and len(kep_adat.berajzolt_szintek) >= 2:
        felette = [x for x in kep_adat.berajzolt_szintek if x > utolso]
        alatta = [x for x in kep_adat.berajzolt_szintek if x < utolso]
        if felette and alatta:
            kezi = (max(alatta), min(felette))
            figy.append(f"A tartomány a képen berajzolt szintekből: {ar(kezi[0])} – {ar(kezi[1])}.")
    tart = tartomany_valaszt(df, eredmenyek, len(jovo), kezi)
    sulyoz = cfg["elorejelzes"]["irany_sulyozas"] if k.irany_sulyozas is None else k.irany_sulyozas
    naplo_kiir("• Monte Carlo szimuláció…")
    eloj = szimulal(df, jovo, tart, kons, eredmenyek, irany_sulyozas=sulyoz)

    # 5. Korábbi elemzés kiértékelése (finomításnál)
    ertekeles = None
    elozmenyek: list[dict] = []
    if szulo:
        ertekeles = kiertekel(szulo, df)
        naplo.ertekeles_ment(szulo.id, ertekeles)
        elozmenyek = [{"id": b.id, "letrehozva": b.letrehozva, "osszegzes": b.osszegzes,
                       "otlet": b.otlet} for b in naplo.lanc(szulo.id)]

    # 6. Elemző agent
    adatcsomag = {
        "szimbolum": szimbolum, "ticker": ticker, "idosik": ids.nev, "horizont": ids.horizont_nev,
        "utolso_ar": utolso, "utolso_gyertya": str(df.index[-1]),
        "adatforras": arf.forras_url, "kep_kiolvasas": kep_adat.model_dump() if kep_adat else None,
        "indikator_konszenzus": kons,
        "indikatorok": [e.json() for e in eredmenyek],
        "elorejelzes": eloj.json(),
        "felhasznalo_elkepzelese": k.otlet or (szulo.otlet if szulo else None),
        "korabbi_elemzesek": [
            {**e, "adatok": naplo.leker(e["id"]).adatok.get("elorejelzes")} for e in elozmenyek
        ],
        "elozo_kiertekelese": ertekeles,
    }
    szoveg, ai_forrasok = None, []
    if k.ai:
        try:
            naplo_kiir("• Elemzés megírása (Claude)…")
            webes = cfg["ai"]["webes_kereses"] if k.webes_kereses is None else k.webes_kereses
            szoveg, ai_forrasok = ai.elemzes_iras(k.kep, adatcsomag, webes)
        except ai.AINemElerheto as e:
            if str(e) not in figy:
                figy.append(str(e))
        except Exception as e:
            figy.append(f"Az AI-elemzés nem sikerült: {e}")
    if not szoveg:
        szoveg = jelentes.automatikus_szoveg(eredmenyek, eloj, kons)

    # 7. Mentés: mappa, chart, jelentés, napló
    eid = naplo.kovetkezo_id()
    mappa = adatkonyvtar() / "elemzesek" / f"{eid:04d}_{ticker.replace('^', '').replace('=', '_')}_{ids.kulcs}"
    mappa.mkdir(parents=True, exist_ok=True)
    kep_fajl = None
    if k.kep:
        kep_fajl = f"kep{k.kep.suffix.lower()}"
        shutil.copy(k.kep, mappa / kep_fajl)

    cim = f"{szimbolum} · {ids.nev} · {ids.horizont_nev}"
    alcim = (f"#{eid} · {ticker} · utolsó ár {ar(utolso)} ({df.index[-1]}) · "
             f"letöltve {arf.letoltve:%Y-%m-%d %H:%M} UTC")
    fig = abra.rajzol(df, eredmenyek, eloj, cim, set(cfg.get("abra", {}).get("lathato", abra.ALAPBOL_LATHATO)))
    oldal = jelentes.html(
        cim=cim, alcim=alcim, fig=fig, eredmenyek=eredmenyek, eloj=eloj, konszenzus=kons,
        szoveg_md=szoveg, ai_forrasok=ai_forrasok, adatforras=(adat.FORRAS_NEV, arf.forras_url),
        otlet=k.otlet, kep_fajl=kep_fajl, elozmenyek=elozmenyek, ertekeles=ertekeles,
        kikapcsolt=[i for i in indikatorok.INDIKATOROK if i not in kulcsok],
    )
    (mappa / "jelentes.html").write_text(oldal, encoding="utf-8")
    (mappa / "elemzes.md").write_text(szoveg, encoding="utf-8")

    fo = next(b for b in eloj.belepesek if b.fo)
    osszegzes = (f"{ids.horizont_nev}: fel {eloj.p_fel:.0%} / oldalaz {eloj.p_bent:.0%} / le "
                 f"{eloj.p_le:.0%} ({ar(tart.also)}–{ar(tart.felso)}); fő terv: {fo.nev} "
                 f"@ {ar(fo.belepo)}, stop {ar(fo.stop)}, cél {ar(fo.cel1)}")
    mentett = naplo.ment(
        szimbolum=szimbolum, ticker=ticker, idosik=ids.kulcs,
        horizont_vege=str(eloj.jovo_idok[-1]), otlet=k.otlet, szulo_id=k.szulo_id,
        mappa=str(mappa), osszegzes=osszegzes,
        adatok={**adatcsomag, "konszenzus": kons, "elemzes_md": szoveg,
                "ai_forrasok": ai_forrasok, "figyelmeztetesek": figy},
    )
    assert mentett == eid, "A napló azonosítója időközben megváltozott"
    return Kimenet(eid, mappa / "jelentes.html", osszegzes, figy)


def kiertekel(b: Bejegyzes, df: pd.DataFrame | None = None) -> dict:
    """Összeveti a mentett előrejelzést a azóta ténylegesen történtekkel."""
    if df is None:
        df = adat.letolt(b.ticker, idosik_keres(b.idosik)).df
    elo = b.adatok["elorejelzes"]
    t = elo["tartomany"]
    kezdet = pd.Timestamp(b.adatok["utolso_gyertya"])
    if df.index.tz is not None and kezdet.tz is None:
        kezdet = kezdet.tz_localize(df.index.tz)
    elif df.index.tz is None and kezdet.tz is not None:
        kezdet = kezdet.tz_localize(None)
    utana = df[df.index > kezdet]
    megall: list[str] = []
    eredmeny = {"gyertyak_azota": len(utana), "megallapitasok": megall}
    if utana.empty:
        megall.append("Az elemzés óta még nem zárult új gyertya.")
        return eredmeny

    ar_most = float(utana["Close"].iloc[-1])
    eredmeny["ar_most"] = ar_most
    fel = utana.index[utana["Close"] > t["felso"]]
    le = utana.index[utana["Close"] < t["also"]]
    if len(fel) and (not len(le) or fel[0] < le[0]):
        tenyleges = "fel"
        megall.append(f"Felfelé tört ki ({fel[0]}), a tartomány teteje {ar(t['felso'])} volt.")
    elif len(le):
        tenyleges = "le"
        megall.append(f"Lefelé tört ki ({le[0]}), a tartomány alja {ar(t['also'])} volt.")
    else:
        tenyleges = "oldalazas"
        megall.append(f"Eddig a tartományon belül maradt ({len(utana)} gyertya).")
    eredmeny["tenyleges"] = tenyleges
    eredmeny["talalat"] = tenyleges == elo["fo_forgatokonyv"]
    p = {"fel": elo["p_fel"], "le": elo["p_le"], "oldalazas": elo["p_bent"]}[tenyleges]
    megall.append(f"A fő forgatókönyv {elo['fo_forgatokonyv']} volt; a ténylegesre ({tenyleges}) "
                  f"{p:.0%} esélyt adtunk.")

    for terv in elo["belepesek"]:
        if not terv["fo"]:
            continue
        hosszu = terv["irany"] == "long"
        aktiv = utana[(utana["High"] >= terv["belepo"]) if hosszu else (utana["Low"] <= terv["belepo"])]
        if aktiv.empty:
            megall.append(f"A fő terv ({terv['nev']}) belépője ({ar(terv['belepo'])}) még nem aktiválódott.")
            continue
        utan = utana.loc[aktiv.index[0]:]
        stop = utan.index[(utan["Low"] <= terv["stop"]) if hosszu else (utan["High"] >= terv["stop"])]
        cel = utan.index[(utan["High"] >= terv["cel1"]) if hosszu else (utan["Low"] <= terv["cel1"])]
        if len(cel) and (not len(stop) or cel[0] < stop[0]):
            kimenet = f"elérte az 1. célt ({ar(terv['cel1'])}) – {cel[0]}"
        elif len(stop):
            kimenet = f"kiütötte a stop ({ar(terv['stop'])}) – {stop[0]}"
        else:
            kimenet = "nyitott, sem cél, sem stop"
        eredmeny["fo_terv"] = kimenet
        megall.append(f"A fő terv ({terv['nev']}) aktiválódott {aktiv.index[0]}; {kimenet}.")

    pc = {int(k): v for k, v in elo["percentilisek_vegen"].items()}
    megall.append(f"Ár most {ar(ar_most)}; a horizont végére jelzett 50%-os sáv "
                  f"{ar(pc[25])}–{ar(pc[75])} volt.")
    return eredmeny
