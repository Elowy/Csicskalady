"""Kitörési valószínűség, szellemgyertyák és belépési tervek Monte Carlo szimulációval.

A módszer: a múltbeli gyertyák (nyitó/csúcs/mélypont/záró az előző záróhoz
viszonyítva) blokkos bootstrap-újramintavételezése (stationary bootstrap), a
jelenlegi volatilitáshoz igazítva, opcionálisan az indikátor-konszenzus
irányába kis sodródással. Minden szimulált pályán megnézzük, hogy a záróár a
köztes tartományt felfelé vagy lefelé hagyja-e el először, vagy a horizont
végéig bent marad.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .indikatorok import Eredmeny, Forras, Szint
from .indikatorok.alap import ar, atr, wiki

PALYAK = 4000
BLOKK = 5                 # átlagos blokkhossz a bootstrapben (volatilitás-klaszterek megőrzése)
IRANY_SULY = 0.1          # konszenzus -> gyertyánkénti sodródás (szórás arányában)
MIN_TAV_ATR = 1.0         # a tartomány széle legalább ennyi ATR-re legyen az ártól
# ...és legalább a horizonton várható mozgás (szórás·√H) ennyiszeresére
MIN_TAV_HORIZONT = 0.5
MIN_EROSSEG = 0.5         # ennél gyengébb szint nem lehet a tartomány széle
MIN_EROSSEG_SR = 0.3


@dataclass
class Tartomany:
    also: float
    felso: float
    also_cimke: str
    felso_cimke: str
    indoklas: str


@dataclass
class Belepes:
    nev: str
    irany: str            # "long" | "short"
    belepo: float
    stop: float
    cel1: float
    cel2: float | None
    valoszinuseg: float   # a forgatókönyv valószínűsége
    fo: bool
    indoklas: str


@dataclass
class Elorejelzes:
    tartomany: Tartomany
    p_fel: float              # először felfelé tör ki
    p_le: float               # először lefelé tör ki
    p_bent: float             # a horizont végéig a tartományban marad
    p_vegen: dict[str, float]  # hol lesz a záróár a horizont végén (fel / bent / le)
    kumulalt_fel: list[float]
    kumulalt_le: list[float]
    jovo_idok: list
    percentilisek: dict[int, list[float]]
    szellem: pd.DataFrame     # OHLC szellemgyertyák
    fo_forgatokonyv: str      # "fel" | "le" | "oldalazas"
    varhato_valtozas_median: float
    belepesek: list[Belepes] = field(default_factory=list)
    modszer: str = ""
    forrasok: list[Forras] = field(default_factory=list)

    def json(self) -> dict:
        return {
            "tartomany": vars(self.tartomany),
            "p_fel": self.p_fel, "p_le": self.p_le, "p_bent": self.p_bent,
            "p_horizont_vegen": self.p_vegen,
            "fo_forgatokonyv": self.fo_forgatokonyv,
            "varhato_valtozas_median": self.varhato_valtozas_median,
            "percentilisek_vegen": {k: v[-1] for k, v in self.percentilisek.items()},
            "belepesek": [vars(b) for b in self.belepesek],
            "horizont_gyertya": len(self.jovo_idok),
            "horizont_vege": str(self.jovo_idok[-1]) if self.jovo_idok else None,
            "modszer": self.modszer,
        }


def tartomany_valaszt(df: pd.DataFrame, eredmenyek: list[Eredmeny], horizont_gyertya: int,
                      kezi: tuple[float, float] | None = None) -> Tartomany:
    utolso = float(df["Close"].iloc[-1])
    a = float(atr(df).iloc[-1])
    szoras = float(np.log(df["Close"]).diff().iloc[-500:].std())
    min_tav = max(MIN_TAV_ATR * a, MIN_TAV_HORIZONT * szoras * np.sqrt(horizont_gyertya) * utolso)
    if kezi:
        lo, hi = sorted(kezi)
        return Tartomany(lo, hi, "kézi alsó", "kézi felső", "A tartományt kézzel adtad meg.")

    def legkozelebbi(jeloltek: list[Szint], tipus: str) -> Szint | None:
        jo = [s for s in jeloltek if s.tipus == tipus and abs(s.ar - utolso) >= min_tav]
        if tipus == "tamasz":
            return max((s for s in jo if s.ar < utolso), key=lambda s: s.ar, default=None)
        return min((s for s in jo if s.ar > utolso), key=lambda s: s.ar, default=None)

    # Jelöltek: minden bekapcsolt modul elég erős szintje (a klasszikus S/R-nél
    # alacsonyabb a küszöb, mert ott az erősség relatív).
    jeloltek = [s for e in eredmenyek if e.alkalmazhato for s in e.szintek
                if s.erosseg >= (MIN_EROSSEG_SR if e.kulcs == "szintek" else MIN_EROSSEG)]
    t = legkozelebbi(jeloltek, "tamasz")
    e = legkozelebbi(jeloltek, "ellenallas")
    lo = t.ar if t else utolso - 1.5 * min_tav
    hi = e.ar if e else utolso + 1.5 * min_tav
    indoklas = (f"Alsó határ: {t.cimke + ' ' + ar(t.ar) if t else f'nincs szint, ár − 1,5×min. távolság ({ar(lo)})'}, "
                f"felső határ: {e.cimke + ' ' + ar(e.ar) if e else f'nincs szint, ár + 1,5×min. távolság ({ar(hi)})'} – "
                f"az aktuális árhoz legközelebbi elég erős támasz és ellenállás bármely bekapcsolt "
                f"modulból, amely legalább {ar(min_tav)} ({min_tav / utolso:.1%}) távolságra van "
                f"(max. {MIN_TAV_ATR:g} ATR és a horizonton várható mozgás {MIN_TAV_HORIZONT:g}-szerese).")
    return Tartomany(lo, hi, t.cimke if t else "alsó sáv", e.cimke if e else "felső sáv", indoklas)


def szimulal(df: pd.DataFrame, jovo_idok: pd.DatetimeIndex, tartomany: Tartomany,
             konszenzus: float, eredmenyek: list[Eredmeny], irany_sulyozas: bool = True,
             mag: int | None = 42) -> Elorejelzes:
    rng = np.random.default_rng(mag)
    h = len(jovo_idok)
    if h == 0:
        raise ValueError("A horizont 0 gyertya – nincs mit előre jelezni.")

    minta = df.iloc[-min(len(df), 1500):]
    elozo = minta["Close"].shift(1)
    rel = np.log(np.column_stack([minta["Open"] / elozo, minta["High"] / elozo,
                                  minta["Low"] / elozo, minta["Close"] / elozo]))[1:]
    rel = rel[np.isfinite(rel).all(axis=1)]
    atlag = rel[:, 3].mean()
    rel = rel - atlag                         # semleges kiindulás: nincs történeti sodródás
    szoras = rel[:, 3].std()
    friss = rel[-50:, 3].std()
    skala = float(np.clip(friss / szoras, 0.5, 2.0)) if szoras > 0 else 1.0
    sodras = (IRANY_SULY * konszenzus * szoras * skala) if irany_sulyozas else 0.0

    # stationary bootstrap indexek
    n = len(rel)
    idx = np.empty((PALYAK, h), dtype=int)
    idx[:, 0] = rng.integers(0, n, PALYAK)
    uj = rng.random((PALYAK, h)) < 1 / BLOKK
    veletlen = rng.integers(0, n, (PALYAK, h))
    for j in range(1, h):
        idx[:, j] = np.where(uj[:, j], veletlen[:, j], (idx[:, j - 1] + 1) % n)
    lepes = rel[idx] * skala + sodras         # (pályák, h, 4)

    c0 = float(df["Close"].iloc[-1])
    zaro_log = np.log(c0) + np.cumsum(lepes[:, :, 3], axis=1)
    elozo_log = np.concatenate([np.full((PALYAK, 1), np.log(c0)), zaro_log[:, :-1]], axis=1)
    o = np.exp(elozo_log + lepes[:, :, 0])
    hi_ = np.exp(elozo_log + lepes[:, :, 1])
    lo_ = np.exp(elozo_log + lepes[:, :, 2])
    c = np.exp(zaro_log)
    hi_ = np.maximum(hi_, np.maximum(o, c))
    lo_ = np.minimum(lo_, np.minimum(o, c))

    fel = c > tartomany.felso
    le = c < tartomany.also
    elso_fel = np.where(fel.any(axis=1), fel.argmax(axis=1), h)
    elso_le = np.where(le.any(axis=1), le.argmax(axis=1), h)
    osztaly = np.where(elso_fel < elso_le, 1, np.where(elso_le < elso_fel, -1, 0))
    p_fel, p_le = float((osztaly == 1).mean()), float((osztaly == -1).mean())
    p_bent = float((osztaly == 0).mean())
    vegen = c[:, -1]
    p_vegen = {"fel": float((vegen > tartomany.felso).mean()),
               "le": float((vegen < tartomany.also).mean())}
    p_vegen["bent"] = float(((vegen >= tartomany.also) & (vegen <= tartomany.felso)).mean())
    kum_fel = [float(((osztaly == 1) & (elso_fel <= j)).mean()) for j in range(h)]
    kum_le = [float(((osztaly == -1) & (elso_le <= j)).mean()) for j in range(h)]

    fo_kod = int(max([(p_fel, 1), (p_le, -1), (p_bent, 0)])[1])
    fo = {1: "fel", -1: "le", 0: "oldalazas"}[fo_kod]
    tag = osztaly == fo_kod
    median_palya = np.median(c[tag], axis=0)
    reprezentans = np.flatnonzero(tag)[np.argmin(((c[tag] - median_palya) ** 2).sum(axis=1))]
    szellem = pd.DataFrame({"Open": o[reprezentans], "High": hi_[reprezentans],
                            "Low": lo_[reprezentans], "Close": c[reprezentans]}, index=jovo_idok)

    percentilisek = {p: list(np.percentile(c, p, axis=0)) for p in (5, 25, 50, 75, 95)}
    varhato = float(np.median(c[:, -1]) / c0 - 1)

    modszer = (f"{PALYAK} szimulált pálya, {h} gyertya előre; az utolsó {len(rel)} gyertya "
               f"OHLC-mozgásainak blokkos bootstrapje (átl. blokk {BLOKK}), a volatilitás az "
               f"utolsó 50 gyertyához igazítva (×{skala:.2f}); "
               + (f"irányított sodródás a konszenzus ({konszenzus:+.2f}) alapján "
                  f"({sodras * 100:+.4f}%/gyertya)." if irany_sulyozas and sodras else
                  "irány-súlyozás nélkül (semleges sodródás).")
               + " Kitörés = záróár a tartományon kívül.")

    eloj = Elorejelzes(tartomany, p_fel, p_le, p_bent, p_vegen, kum_fel, kum_le, list(jovo_idok),
                       percentilisek, szellem, fo, varhato, modszer=modszer,
                       forrasok=[wiki("Monte Carlo method in finance", "Monte_Carlo_methods_in_finance"),
                                 wiki("Bootstrapping (statistics)", "Bootstrapping_(statistics)")])
    eloj.belepesek = belepesi_tervek(df, eloj, eredmenyek)
    return eloj


def belepesi_tervek(df: pd.DataFrame, eloj: Elorejelzes, eredmenyek: list[Eredmeny]) -> list[Belepes]:
    a = float(atr(df).iloc[-1])
    t = eloj.tartomany
    szel = t.felso - t.also
    szintek = sorted({s.ar for e in eredmenyek if e.alkalmazhato for s in e.szintek})

    def cel(belepo: float, stop: float, felfele: bool, kivetites: float) -> float:
        """Az első szint a belépőn túl, ami legalább akkora hozamot ad, mint a kockázat."""
        kockazat = abs(belepo - stop)
        jo = [s for s in szintek if (s - belepo if felfele else belepo - s) >= max(kockazat, a)]
        # a legközelebbi megfelelő szint, de legfeljebb a tartomány kivetítéséig
        return min(jo + [kivetites]) if felfele else max(jo + [kivetites])

    fel_be, fel_stop = t.felso + 0.1 * a, max(t.also, t.felso - 1.5 * a)
    le_be, le_stop = t.also - 0.1 * a, min(t.felso, t.also + 1.5 * a)
    fel_cel1 = cel(fel_be, fel_stop, True, t.felso + szel)
    le_cel1 = cel(le_be, le_stop, False, t.also - szel)
    tervek = [
        Belepes("Kitörés felfelé", "long", fel_be, fel_stop, fel_cel1, max(t.felso + szel, fel_cel1), eloj.p_fel, eloj.fo_forgatokonyv == "fel",
                f"Vételi stop a {t.felso_cimke} ({ar(t.felso)}) fölött 0,1 ATR-rel; érvényes "
                f"kitörés a záróár a szint felett. 1. cél ({ar(fel_cel1)}) az első szint, amely "
                f"legalább a kockázattal azonos hozamot ad (legfeljebb a kivetítésig), "
                f"2. cél a tartomány szélességének kivetítése ({ar(t.felso + szel)}). "
                f"Stop 1,5 ATR-rel a kitört szint alatt (de legfeljebb az alsó határon)."),
        Belepes("Kitörés lefelé", "short", le_be, le_stop, le_cel1, min(t.also - szel, le_cel1), eloj.p_le, eloj.fo_forgatokonyv == "le",
                f"Eladási stop a {t.also_cimke} ({ar(t.also)}) alatt 0,1 ATR-rel. 1. cél "
                f"{ar(le_cel1)} (legalább 1:1 hozam/kockázat), 2. cél a tartomány kivetítése ({ar(t.also - szel)}). "
                "Stop 1,5 ATR-rel a letört szint felett."),
        Belepes("Oldalazás – vétel a támasznál", "long", t.also + 0.15 * a, t.also - 1.0 * a,
                t.also + szel / 2, t.felso - 0.15 * a, eloj.p_bent, eloj.fo_forgatokonyv == "oldalazas",
                f"Tartományon belüli kereskedés: limit vétel a {t.also_cimke} felett, cél a "
                "tartomány közepe, majd a teteje; stop 1 ATR-rel a támasz alatt."),
        Belepes("Oldalazás – eladás az ellenállásnál", "short", t.felso - 0.15 * a, t.felso + 1.0 * a,
                t.felso - szel / 2, t.also + 0.15 * a, eloj.p_bent, False,
                f"Limit eladás a {t.felso_cimke} alatt, cél a tartomány közepe, majd az alja; "
                "stop 1 ATR-rel az ellenállás felett."),
    ]
    return tervek
