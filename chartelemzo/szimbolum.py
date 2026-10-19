"""TradingView szimbólumok átfordítása Yahoo Finance tickerre."""

from __future__ import annotations

import re

# TradingView tőzsdekód -> Yahoo utótag
_TOZSDE_UTOTAG = {
    "NASDAQ": "", "NYSE": "", "AMEX": "", "NYSEARCA": "", "CBOE": "", "OTC": "",
    "BET": ".BD", "BSE": ".BD",          # Budapesti Értéktőzsde
    "XETR": ".DE", "FWB": ".F", "GETTEX": ".DE",
    "LSE": ".L", "LSIN": ".L",
    "EURONEXT": ".PA", "EPA": ".PA", "EBR": ".BR", "AMS": ".AS",
    "MIL": ".MI", "BME": ".MC", "SIX": ".SW", "VIE": ".VI",
    "GPW": ".WA", "WSE": ".WA", "PSE": ".PR",
    "TSX": ".TO", "TSXV": ".V", "ASX": ".AX", "TSE": ".T", "HKEX": ".HK",
}

# Nyersanyagok és indexek (TradingView -> Yahoo)
_KULONLEGES = {
    "XAUUSD": "GC=F", "GOLD": "GC=F", "XAGUSD": "SI=F", "SILVER": "SI=F",
    "USOIL": "CL=F", "WTI": "CL=F", "UKOIL": "BZ=F", "BRENT": "BZ=F",
    "NATGAS": "NG=F", "COPPER": "HG=F", "XPTUSD": "PL=F", "XPDUSD": "PA=F",
    "SPX": "^GSPC", "SPX500": "^GSPC", "US500": "^GSPC", "NDX": "^NDX",
    "NAS100": "^NDX", "DJI": "^DJI", "US30": "^DJI", "DAX": "^GDAXI",
    "GER40": "^GDAXI", "DE40": "^GDAXI", "UKX": "^FTSE", "VIX": "^VIX",
    "DXY": "DX-Y.NYB", "BUX": "^BUX.BD",
}

_KRIPTO_TOZSDEK = {"BINANCE", "COINBASE", "BYBIT", "KRAKEN", "BITSTAMP", "OKX",
                   "BITFINEX", "KUCOIN", "CRYPTO", "CRYPTOCAP", "GEMINI", "MEXC"}
_FOREX_TOZSDEK = {"FX", "FX_IDC", "OANDA", "FXCM", "PEPPERSTONE", "SAXO", "ICMARKETS"}
_KRIPTO_JEGYZES = ("USDT", "USDC", "BUSD", "FDUSD", "USD", "EUR", "BTC", "ETH")
_DEVIZAK = {"USD", "EUR", "GBP", "JPY", "CHF", "AUD", "NZD", "CAD", "HUF", "PLN",
            "CZK", "SEK", "NOK", "DKK", "TRY", "ZAR", "MXN", "CNH", "SGD", "HKD"}


def yahoo_ticker(szimbolum: str, eszkozosztaly: str | None = None) -> str:
    """Pl. "NASDAQ:AAPL" -> "AAPL", "BINANCE:BTCUSDT" -> "BTC-USD",
    "FX:EURUSD" -> "EURUSD=X", "COMEX:GC1!" -> "GC=F", "BET:OTP" -> "OTP.BD".

    A már Yahoo-formátumú tickereket (pl. "BTC-USD", "EURUSD=X", "OTP.BD")
    változatlanul hagyja.
    """
    s = szimbolum.strip().upper()
    if not s:
        raise ValueError("Üres szimbólum")
    if ":" in s:
        tozsde, ticker = s.split(":", 1)
    else:
        tozsde, ticker = "", s

    if not tozsde and re.search(r"[=^]|-USD$|-EUR$|\.[A-Z]{1,3}$", ticker):
        return ticker

    if ticker in _KULONLEGES:
        return _KULONLEGES[ticker]

    # Folyamatos határidős jelölés: GC1!, CL1!, ES1!
    m = re.fullmatch(r"([A-Z]{1,3})\d!", ticker)
    if m:
        return f"{m.group(1)}=F"

    osztaly = (eszkozosztaly or "").lower()
    if tozsde in _KRIPTO_TOZSDEK or osztaly == "kripto":
        for jegyzes in _KRIPTO_JEGYZES:
            if ticker.endswith(jegyzes) and len(ticker) > len(jegyzes):
                alap = ticker[: -len(jegyzes)]
                penz = "EUR" if jegyzes == "EUR" else (jegyzes if jegyzes in ("BTC", "ETH") else "USD")
                return f"{alap}-{penz}"
        return f"{ticker}-USD"

    if (tozsde in _FOREX_TOZSDEK or osztaly == "deviza") or (
        len(ticker) == 6 and ticker[:3] in _DEVIZAK and ticker[3:] in _DEVIZAK
    ):
        return f"{ticker}=X"

    utotag = _TOZSDE_UTOTAG.get(tozsde, "")
    return ticker.replace(".", "-") + utotag
