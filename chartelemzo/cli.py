"""Parancssori felület.

Példák:
  chartelemzo elemez kep.png
  chartelemzo elemez kep.png --idosik 1d --otlet "Szerintem 200 fölé megy nyárig"
  chartelemzo elemez --szimbolum BINANCE:BTCUSDT --idosik 4h --ki elliott,fibonacci
  chartelemzo naplo
  chartelemzo mutat 3
  chartelemzo finomit 3 --otlet "Azóta jött egy jó negyedéves jelentés" [--kep uj.png]
  chartelemzo ellenoriz 3
  chartelemzo indikatorok
"""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path

from . import folyamat, indikatorok
from .idosikok import IDOSIKOK
from .naplo import Naplo


def _lista(s: str | None) -> list[str]:
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _tartomany(s: str | None) -> tuple[float, float] | None:
    if not s:
        return None
    a, b = (float(x.replace(",", ".")) for x in s.replace(" ", "").split(":"))
    return (a, b)


def _kozos(p: argparse.ArgumentParser) -> None:
    p.add_argument("--szimbolum", help="TradingView vagy Yahoo szimbólum, pl. NASDAQ:AAPL, BET:OTP, BTC-USD")
    p.add_argument("--idosik", help=f"Idősík: {', '.join(IDOSIKOK)}")
    p.add_argument("--otlet", help="Saját elképzelésed, amit naplózunk és az elemzés értékel")
    p.add_argument("--be", help="Bekapcsolandó indikátorok vesszővel")
    p.add_argument("--ki", help="Kikapcsolandó indikátorok vesszővel")
    p.add_argument("--tartomany", help="Köztes tartomány kézzel, pl. 180:195")
    p.add_argument("--ai-nelkul", action="store_true", help="Claude nélkül (csak számítás)")
    p.add_argument("--web-nelkul", action="store_true", help="Ne keressen a weben")
    p.add_argument("--semleges", action="store_true", help="Szimuláció irány-súlyozás nélkül")
    p.add_argument("--megnyit", action="store_true", help="A jelentés megnyitása böngészőben")


def _futtat(args, kep: Path | None, szulo_id: int | None = None) -> None:
    k = folyamat.Keres(
        kep=kep, szimbolum=args.szimbolum, idosik=args.idosik, otlet=args.otlet,
        be=_lista(args.be), ki=_lista(args.ki), tartomany=_tartomany(args.tartomany),
        ai=not args.ai_nelkul, webes_kereses=False if args.web_nelkul else None,
        irany_sulyozas=False if args.semleges else None, szulo_id=szulo_id,
    )
    ki = folyamat.elemez(k)
    for f in ki.figyelmeztetesek:
        print(f"! {f}")
    print(f"\n#{ki.id} {ki.osszegzes}\nJelentés: {ki.jelentes}")
    if args.megnyit:
        webbrowser.open(ki.jelentes.as_uri())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="chartelemzo", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    al = p.add_subparsers(dest="parancs", required=True)

    e = al.add_parser("elemez", help="Új elemzés képből és/vagy szimbólumból")
    e.add_argument("kep", nargs="?", type=Path, help="TradingView képernyőkép (png/jpg)")
    _kozos(e)

    f = al.add_parser("finomit", help="Korábbi elemzés finomítása friss adattal / új infóval")
    f.add_argument("id", type=int)
    f.add_argument("--kep", type=Path, help="Új képernyőkép (opcionális)")
    _kozos(f)

    n = al.add_parser("naplo", help="Korábbi elemzések listája")
    n.add_argument("--szimbolum")
    n.add_argument("--keres", help="Szabad szöveges keresés az elképzelésekben/összegzésekben")

    m = al.add_parser("mutat", help="Egy elemzés részletei")
    m.add_argument("id", type=int)
    m.add_argument("--megnyit", action="store_true")

    c = al.add_parser("ellenoriz", help="Bejött-e az előrejelzés? (friss adattal)")
    c.add_argument("id", type=int)

    al.add_parser("indikatorok", help="Elérhető indikátorok")

    args = p.parse_args(argv)
    try:
        if args.parancs == "elemez":
            if not args.kep and not args.szimbolum:
                p.error("Adj meg képet vagy --szimbolum-ot.")
            _futtat(args, args.kep)
        elif args.parancs == "finomit":
            _futtat(args, args.kep, szulo_id=args.id)
        elif args.parancs == "naplo":
            for b in Naplo().lista(args.szimbolum, args.keres):
                szulo = f" ← #{b.szulo_id}" if b.szulo_id else ""
                print(f"#{b.id:<4} {b.letrehozva[:16]}  {b.szimbolum:<18} {b.idosik:<4}{szulo}\n"
                      f"      {b.osszegzes}" + (f"\n      Ötlet: {b.otlet}" if b.otlet else ""))
        elif args.parancs == "mutat":
            naplo = Naplo()
            b = naplo.leker(args.id)
            print(f"#{b.id} {b.szimbolum} ({b.ticker}) {b.idosik}, {b.letrehozva}")
            print(f"Horizont vége: {b.horizont_vege}\n{b.osszegzes}")
            if b.otlet:
                print(f"Ötlet: {b.otlet}")
            for ert in naplo.ertekelesek(b.id):
                print(f"Kiértékelés {ert['idopont']}:")
                for s in ert.get("megallapitasok", []):
                    print(f"  - {s}")
            jel = Path(b.mappa) / "jelentes.html"
            print(f"Jelentés: {jel}")
            if args.megnyit:
                webbrowser.open(jel.as_uri())
        elif args.parancs == "ellenoriz":
            naplo = Naplo()
            ert = folyamat.kiertekel(naplo.leker(args.id))
            naplo.ertekeles_ment(args.id, ert)
            for s in ert["megallapitasok"]:
                print(f"- {s}")
        elif args.parancs == "indikatorok":
            alap = set(folyamat.beallitasok()["indikatorok"]["alapbol"])
            for i in indikatorok.INDIKATOROK.values():
                print(f"{'[x]' if i.kulcs in alap else '[ ]'} {i.kulcs:<15} {i.nev} – {i.leiras}")
    except (ValueError, KeyError, RuntimeError) as hiba:
        print(f"Hiba: {hiba}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
