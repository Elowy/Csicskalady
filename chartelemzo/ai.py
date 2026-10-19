"""Claude-alapú agentek: kép-kiolvasó és magyar nyelvű elemző (webes forrásokkal)."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

MODELL = os.environ.get("CHARTELEMZO_MODELL", "claude-opus-5-5")
# Ha a biztonsági szűrő elutasítana egy kérést, a szerver automatikusan
# egy ajánlott tartalék modellen futtatja újra.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AINemElerheto(RuntimeError):
    pass


class KepAdatok(BaseModel):
    """Amit a TradingView képernyőképről ki lehet olvasni."""
    szimbolum: str | None = Field(description="TradingView szimbólum tőzsdével, pl. 'NASDAQ:AAPL', "
                                              "'BINANCE:BTCUSDT', 'FX:EURUSD', 'BET:OTP'")
    eszkozosztaly: Literal["reszveny", "kripto", "deviza", "nyersanyag", "index", "ismeretlen"]
    idosik: str | None = Field(description="A chart felbontása: 1w, 1d, 4h, 1h, 15m vagy 5m")
    utolso_ar: float | None = Field(description="A jobb oldali árskálán kiemelt aktuális ár")
    lathato_tol: str | None = Field(description="A látható időszak eleje (dátum, ha olvasható)")
    lathato_ig: str | None = Field(description="A látható időszak vége (dátum, ha olvasható)")
    berajzolt_szintek: list[float] = Field(description="A felhasználó által berajzolt vízszintes "
                                                       "vonalak árai, ha vannak")
    megjegyzes: str = Field(description="Rövid magyar leírás arról, mi látszik a charton "
                                        "(indikátorok, rajzok, alakzatok)")
    biztonsag: float = Field(description="0..1, mennyire biztos a szimbólum és idősík kiolvasása")


def _kliens():
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise AINemElerheto("Az 'anthropic' csomag nincs telepítve.") from e
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise AINemElerheto("Nincs ANTHROPIC_API_KEY beállítva – az AI-lépések kimaradnak.")
    return anthropic.Anthropic()


def _kep_blokk(kep: Path) -> dict:
    tipus = mimetypes.guess_type(kep.name)[0] or "image/png"
    adat = base64.standard_b64encode(kep.read_bytes()).decode()
    return {"type": "image", "source": {"type": "base64", "media_type": tipus, "data": adat}}


def _elutasitas(valasz) -> None:
    if valasz.stop_reason == "refusal":
        reszlet = getattr(valasz, "stop_details", None)
        raise RuntimeError(f"A modell elutasította a kérést ({getattr(reszlet, 'category', None)}).")


def kep_kiolvas(kep: Path) -> KepAdatok:
    kliens = _kliens()
    valasz = kliens.beta.messages.parse(
        model=MODELL,
        max_tokens=4000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": "low"},
        output_format=KepAdatok,
        messages=[{"role": "user", "content": [
            _kep_blokk(kep),
            {"type": "text", "text": (
                "Ez egy TradingView chart képernyőképe. Olvasd ki róla a szimbólumot (a bal "
                "felső sarokban, tőzsdével együtt), az idősíkot, az aktuális árat, a látható "
                "időszakot és a felhasználó által berajzolt vízszintes szinteket. Ami nem "
                "olvasható, legyen null.")},
        ]}],
    )
    _elutasitas(valasz)
    return valasz.parsed_output


ELEMZO_RENDSZER = """Tapasztalt technikai elemző vagy, aki magyarul ír egyetlen felhasználónak.
Kapsz egy TradingView képernyőképet, a számszerű indikátor-eredményeket (mindegyik saját
indoklással), egy Monte Carlo alapú kitörési valószínűséget és belépési terveket.

Feladat:
- Írj tömör, jól tagolt magyar elemzést Markdownban ezekkel a fejezetekkel:
  ## Összkép, ## Szintek és indoklásuk, ## Forgatókönyvek (felfelé kitörés / lefelé kitörés /
  oldalazás, mindegyiknél a valószínűség, a belépő, a stop és a cél), ## Fundamentális és
  hírháttér, ## Kockázatok és érvénytelenítés, ## Források.
- Minden szintnél és indikátornál indokold meg, miért éppen arra az árra és miért erre az
  eszközre vonatkozik (érintések, időpontok, számok a kapott adatokból).
- A számokat a kapott adatokból vedd; ne találj ki árakat. Ha a kép és az adat eltér, jelezd.
- Ha engedélyezett, keress a weben friss híreket/fundamentumokat az eszközről, és hivatkozz
  rájuk. A ## Források fejezetben sorold fel a felhasznált forrásokat linkkel.
- Ha a felhasználónak van saját elképzelése, értékeld őszintén: mi támasztja alá, mi szól ellene.
- Ha korábbi elemzés és annak kiértékelése is adott, vesd össze: mi jött be, mi nem, és
  ennek fényében finomítsd az előrejelzést.
- Ha az Elliott-modul be van kapcsolva, adj óvatos hullámszámlálást a megadott fordulópontokból.
- A végén egy mondatban jelezd, hogy ez nem befektetési tanácsadás."""


def elemzes_iras(kep: Path | None, adatcsomag: dict, webes_kereses: bool = True) -> tuple[str, list[dict]]:
    """Visszaadja a Markdown szöveget és a webes hivatkozások listáját."""
    kliens = _kliens()
    tartalom: list[dict] = []
    if kep is not None:
        tartalom.append(_kep_blokk(kep))
    tartalom.append({"type": "text", "text":
                     "Az elemzés adatai (JSON):\n```json\n"
                     + json.dumps(adatcsomag, ensure_ascii=False, indent=1, default=str)
                     + "\n```"})
    uzenetek = [{"role": "user", "content": tartalom}]
    eszkozok = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 5}] if webes_kereses else []

    blokkok = []
    for _ in range(5):  # pause_turn esetén folytatjuk
        with kliens.beta.messages.stream(
            model=MODELL, max_tokens=32000, system=ELEMZO_RENDSZER, messages=uzenetek,
            tools=eszkozok, betas=[FALLBACK_BETA], fallbacks="default",
            thinking={"type": "adaptive"}, output_config={"effort": "high"},
        ) as folyam:
            valasz = folyam.get_final_message()
        _elutasitas(valasz)
        blokkok.extend(valasz.content)
        if valasz.stop_reason != "pause_turn":
            break
        uzenetek.append({"role": "assistant", "content": valasz.content})

    szoveg, hivatkozasok = [], {}
    for blokk in blokkok:
        if blokk.type == "text":
            szoveg.append(blokk.text)
            for c in getattr(blokk, "citations", None) or []:
                url = getattr(c, "url", None)
                if url:
                    hivatkozasok[url] = {"cim": getattr(c, "title", url), "url": url}
    return "".join(szoveg), list(hivatkozasok.values())
