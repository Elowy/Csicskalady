import numpy as np
import pandas as pd
import pytest

from chartelemzo import adat, folyamat, indikatorok
from chartelemzo.elorejelzes import szimulal, tartomany_valaszt
from chartelemzo.idosikok import IDOSIKOK, idosik
from chartelemzo.indikatorok.alap import Kontextus
from chartelemzo.naplo import Naplo
from chartelemzo.szimbolum import yahoo_ticker


@pytest.mark.parametrize("be, ki", [
    ("NASDAQ:AAPL", "AAPL"), ("BINANCE:BTCUSDT", "BTC-USD"), ("COINBASE:ETHEUR", "ETH-EUR"),
    ("FX:EURUSD", "EURUSD=X"), ("OANDA:XAUUSD", "GC=F"), ("COMEX:GC1!", "GC=F"),
    ("BET:OTP", "OTP.BD"), ("XETR:SAP", "SAP.DE"), ("NYSE:BRK.B", "BRK-B"),
    ("BTC-USD", "BTC-USD"), ("EURHUF", "EURHUF=X"), ("TVC:USOIL", "CL=F"),
])
def test_yahoo_ticker(be, ki):
    assert yahoo_ticker(be) == ki


def test_idosik_aliasok():
    assert idosik("D").kulcs == "1d"
    assert idosik("240").kulcs == "4h"
    with pytest.raises(ValueError):
        idosik("3h")


def _szintetikus(n=600, freq="1D", mag=1, napi_hetkoznap=True) -> pd.DataFrame:
    rng = np.random.default_rng(mag)
    idx = pd.bdate_range("2023-01-02", periods=n) if napi_hetkoznap else pd.date_range(
        "2024-01-01", periods=n, freq=freq)
    c = 100 * np.exp(np.cumsum(rng.normal(0.0003, 0.015, n)))
    o = np.r_[c[0], c[:-1]] * np.exp(rng.normal(0, 0.003, n))
    h = np.maximum(o, c) * np.exp(np.abs(rng.normal(0, 0.006, n)))
    l = np.minimum(o, c) * np.exp(-np.abs(rng.normal(0, 0.006, n)))
    return pd.DataFrame({"Open": o, "High": h, "Low": l, "Close": c,
                         "Volume": rng.integers(1e5, 1e6, n).astype(float)}, index=idx)


def test_jovobeli_index_napos_kihagyja_hetveget():
    df = _szintetikus()
    jovo = adat.jovobeli_index(df, IDOSIKOK["1d"])
    assert 60 <= len(jovo) <= 67
    assert all(t.weekday() < 5 for t in jovo)


def test_jovobeli_index_5perc_aktiv_ido():
    df = _szintetikus(3000, "5min", napi_hetkoznap=False)
    assert len(adat.jovobeli_index(df, IDOSIKOK["5m"])) == 96


def test_indikatorok_es_szimulacio():
    df = _szintetikus()
    jovo = adat.jovobeli_index(df, IDOSIKOK["1d"])
    ktx = Kontextus("TESZT", "napos", True, len(jovo))
    eredm = indikatorok.futtat(df, ktx, list(indikatorok.INDIKATOROK))
    assert all("Hiba" not in e.osszegzes for e in eredm), [e.osszegzes for e in eredm]
    for e in eredm:
        if e.alkalmazhato and e.kulcs not in ("atr", "gyertyaalakzat", "elliott"):
            assert e.indoklasok, f"{e.kulcs}: hiányzó indoklás"
        assert e.forrasok, f"{e.kulcs}: hiányzó forrás"

    tart = tartomany_valaszt(df, eredm, len(jovo))
    utolso = df["Close"].iloc[-1]
    assert tart.also < utolso < tart.felso
    eloj = szimulal(df, jovo, tart, indikatorok.konszenzus(eredm), eredm)
    assert abs(eloj.p_fel + eloj.p_le + eloj.p_bent - 1) < 1e-9
    assert len(eloj.szellem) == len(jovo)
    assert (eloj.szellem["High"] >= eloj.szellem[["Open", "Close"]].max(axis=1)).all()
    assert sum(b.fo for b in eloj.belepesek) == 1


def test_kezi_tartomany():
    df = _szintetikus()
    t = tartomany_valaszt(df, [], 60, kezi=(120.0, 90.0))
    assert (t.also, t.felso) == (90.0, 120.0)


def test_teljes_folyamat_es_naplo(tmp_path, monkeypatch):
    monkeypatch.setenv("CHARTELEMZO_ADAT", str(tmp_path))
    df = _szintetikus()
    monkeypatch.setattr(adat, "letolt", lambda t, i: adat.Arfolyam(t, i, df, pd.Timestamp.now(tz="UTC")))
    naplo = Naplo(tmp_path / "naplo.db")

    ki = folyamat.elemez(folyamat.Keres(szimbolum="NASDAQ:TESZT", idosik="1d", otlet="Felfelé!",
                                        ai=False, ki=["elliott"]), naplo, naplo_kiir=lambda *_: None)
    assert ki.jelentes.exists()
    html = ki.jelentes.read_text("utf-8")
    assert "Felfelé kitörés" in html and "Szellemgyerty" in html

    # finomítás: a szülő kiértékelődik és láncba kerül
    ki2 = folyamat.elemez(folyamat.Keres(otlet="Új infó", ai=False, szulo_id=ki.id), naplo,
                          naplo_kiir=lambda *_: None)
    lanc = naplo.lanc(ki2.id)
    assert [b.id for b in lanc] == [ki.id, ki2.id]
    assert naplo.ertekelesek(ki.id)
    assert naplo.lista(keres="Új infó")[0].id == ki2.id
