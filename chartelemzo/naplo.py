"""Elemzési napló: minden elemzés és elképzelés visszakereshető, finomítható."""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SEMA = """
CREATE TABLE IF NOT EXISTS elemzesek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    letrehozva TEXT NOT NULL,
    szimbolum TEXT NOT NULL,
    ticker TEXT NOT NULL,
    idosik TEXT NOT NULL,
    horizont_vege TEXT,
    otlet TEXT,
    szulo_id INTEGER REFERENCES elemzesek(id),
    mappa TEXT NOT NULL,
    osszegzes TEXT,
    adatok TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ertekelesek (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    elemzes_id INTEGER NOT NULL REFERENCES elemzesek(id),
    idopont TEXT NOT NULL,
    adatok TEXT NOT NULL
);
"""


def adatkonyvtar() -> Path:
    p = Path(os.environ.get("CHARTELEMZO_ADAT", "adatok")).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class Bejegyzes:
    id: int
    letrehozva: str
    szimbolum: str
    ticker: str
    idosik: str
    horizont_vege: str | None
    otlet: str | None
    szulo_id: int | None
    mappa: str
    osszegzes: str | None
    adatok: dict


class Naplo:
    def __init__(self, utvonal: Path | None = None):
        self.utvonal = utvonal or adatkonyvtar() / "naplo.db"
        self.db = sqlite3.connect(self.utvonal)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SEMA)

    def kovetkezo_id(self) -> int:
        sor = self.db.execute("SELECT seq FROM sqlite_sequence WHERE name='elemzesek'").fetchone()
        return (sor["seq"] if sor else 0) + 1

    def ment(self, *, szimbolum: str, ticker: str, idosik: str, horizont_vege: str | None,
             otlet: str | None, szulo_id: int | None, mappa: str, osszegzes: str,
             adatok: dict) -> int:
        kurzor = self.db.execute(
            "INSERT INTO elemzesek (letrehozva, szimbolum, ticker, idosik, horizont_vege, otlet,"
            " szulo_id, mappa, osszegzes, adatok) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), szimbolum, ticker, idosik,
             horizont_vege, otlet, szulo_id, mappa, osszegzes,
             json.dumps(adatok, ensure_ascii=False, default=str)),
        )
        self.db.commit()
        return int(kurzor.lastrowid)

    def ertekeles_ment(self, elemzes_id: int, adatok: dict) -> None:
        self.db.execute("INSERT INTO ertekelesek (elemzes_id, idopont, adatok) VALUES (?,?,?)",
                        (elemzes_id, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                         json.dumps(adatok, ensure_ascii=False, default=str)))
        self.db.commit()

    def _bejegyzes(self, sor: sqlite3.Row) -> Bejegyzes:
        d = dict(sor)
        d["adatok"] = json.loads(d["adatok"])
        return Bejegyzes(**d)

    def leker(self, elemzes_id: int) -> Bejegyzes:
        sor = self.db.execute("SELECT * FROM elemzesek WHERE id=?", (elemzes_id,)).fetchone()
        if sor is None:
            raise KeyError(f"Nincs #{elemzes_id} azonosítójú elemzés a naplóban.")
        return self._bejegyzes(sor)

    def lista(self, szimbolum: str | None = None, keres: str | None = None,
              limit: int = 50) -> list[Bejegyzes]:
        feltetel, param = [], []
        if szimbolum:
            feltetel.append("(szimbolum LIKE ? OR ticker LIKE ?)")
            param += [f"%{szimbolum}%"] * 2
        if keres:
            feltetel.append("(otlet LIKE ? OR osszegzes LIKE ?)")
            param += [f"%{keres}%"] * 2
        where = f"WHERE {' AND '.join(feltetel)}" if feltetel else ""
        sorok = self.db.execute(f"SELECT * FROM elemzesek {where} ORDER BY id DESC LIMIT ?",
                                (*param, limit)).fetchall()
        return [self._bejegyzes(s) for s in sorok]

    def lanc(self, elemzes_id: int) -> list[Bejegyzes]:
        """Az elemzés és összes őse (legrégebbi elöl) – a finomítások története."""
        lanc, akt = [], self.leker(elemzes_id)
        while True:
            lanc.append(akt)
            if akt.szulo_id is None:
                break
            akt = self.leker(akt.szulo_id)
        return lanc[::-1]

    def ertekelesek(self, elemzes_id: int) -> list[dict]:
        sorok = self.db.execute("SELECT * FROM ertekelesek WHERE elemzes_id=? ORDER BY id",
                                (elemzes_id,)).fetchall()
        return [{"idopont": s["idopont"], **json.loads(s["adatok"])} for s in sorok]
