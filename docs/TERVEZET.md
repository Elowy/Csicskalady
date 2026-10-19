# Tervezet

## Döntések (az első egyeztetés alapján)

| Kérdés | Döntés |
|---|---|
| Felhasználó | csak én (egyfelhasználós, helyi futtatás) |
| Bemenet | tiszta TradingView-képernyőkép; a szimbólum és az idősík kézzel is megadható |
| Piacok | részvény, kripto, deviza, nyersanyag |
| Horizontok | heti → 1 év, napos → 3 hónap, 4 órás → 1 hónap, órás → 2 hét, 15 perces → 1 nap, 5 perces → 8 óra |
| Adat | friss árfolyam az internetről (Yahoo Finance) |
| Indikátorok | mind benne van, ki- és bekapcsolhatók, mindegyiknek indokolnia kell a szintjét |
| Forgatókönyvek | long, short, oldalazás |
| Megjelenítés | interaktív chart szellemgyertyákkal |
| Szöveg | magyarul, forrásmegjelöléssel és indoklással |
| Kockázatkezelés (pozícióméret) | nem kell |
| Nyelv / AI | Python / Claude |
| Napló | igen: az elképzelések elmentve, visszakereshetők, finomíthatók |

## Felépítés

```
kép ──► [1] Kép-kiolvasó agent (Claude, vision, strukturált kimenet)
            szimbólum, idősík, aktuális ár, berajzolt szintek
                 │
                 ▼
        [2] Adat (yfinance) ──► TradingView→Yahoo szimbólumfordítás, 4h átmintázás,
                 │               jövőbeli időtengely a kereskedési órák szerint
                 ▼
        [3] Indikátor-modulok (determinisztikus, kapcsolhatók)
            szintek · fibonacci · mozgóátlag · rsi · macd · bollinger · atr ·
            volumenprofil · gyertyaalakzat · trendcsatorna · alakzat · elliott(AI)
            → mindegyik: szintek + indoklás + irány (−1…+1) + források
                 │
                 ▼
        [4] Előrejelzés (Monte Carlo, blokkos bootstrap)
            köztes tartomány → P(fel), P(le), P(oldalaz), kumulált görbék,
            percentilis-legyező, szellemgyertyák, belépési tervek
                 │
                 ▼
        [5] Elemző agent (Claude, webes kereséssel)
            magyar szöveg, forgatókönyvek, hírek/fundamentumok, források;
            a saját elképzelés és a korábbi elemzések értékelése
                 │
                 ▼
        [6] Jelentés (HTML + Plotly) és napló (SQLite)
```

Az LLM nem számol árszinteket. A számokat a determinisztikus modulok állítják elő,
így a jelentésben szereplő minden szint visszakereshető és ellenőrizhető. Claude két
feladatot kap: kiolvassa a képet, és értelmez, összevet, illetve forrásokat keres.

## A „köztes tartomány” és a kitörési esély

- **Tartomány:** az aktuális árhoz legközelebbi, elég erős támasz és ellenállás bármely
  bekapcsolt modulból. A szélének legalább `max(1 ATR, 0,5 · σ · √H)` távolságra kell
  lennie az ártól, hogy hosszú horizonton is értelmes legyen. A tartomány megadható kézzel
  (`--tartomany`), és ha a képen két berajzolt vízszintes vonal fogja közre az árat, a
  program azokat használja.
- **Szimuláció:** 4000 pálya. A múltbeli gyertyák nyitó-, csúcs-, mélypont- és záróárait
  blokkokban mintavételezi újra (átlagos blokkhossz 5), és a volatilitást az utolsó 50
  gyertyához igazítja. Opcionálisan enyhe sodródást ad az indikátor-konszenzus irányába.
- **Kitörés:** a záróár a tartományon kívül zár. Pályánként azt rögzíti, melyik oldalon
  történik meg először.
- **Szellemgyertyák:** a legvalószínűbb kimenetelű pályák közül az, amelyik a medián
  pályához a legközelebb fut. Így valósághű gyertyák jönnek ki, nem egy kisimított vonal.

## Napló és finomítás

- `elemez` ment: az összes bemenet, indikátor, valószínűség és belépő JSON-ként, valamint a jelentés.
- `ellenoriz <id>`: friss adattal megnézi, merre tört ki ténylegesen az ár, aktiválódott-e
  a fő terv, és elérte-e a célt vagy a stopot.
- `finomit <id>`: új elemzés ugyanarra az eszközre. A szülőt előbb kiértékeli, majd a teljes
  láncot (korábbi elképzelések, előrejelzések, kiértékelések) átadja Claude-nak, hogy
  ezek fényében pontosítson.

## Következő lépések (javaslat)

1. **Kalibráció / visszamérés.** A napló kiértékeléseiből látható, mennyire jók a
   valószínűségek (például Brier-pontszám idősíkonként). Ezek alapján hangolható a
   sodródás súlya és a tartomány-választás.
2. **Kényelmes beküldés.** Egy Telegram-bot (fotó → jelentés linkje) vagy egy egyszerű
   Streamlit-felület, hogy telefonról is lehessen képet küldeni.
3. **Több adatforrás.** BÉT-papíroknál és perces kriptoadatnál a Yahoo hiányos lehet;
   szóba jöhet a Binance API vagy a Twelve Data.
4. **Ütemezett ellenőrzés.** Naponta egyszer automatikusan lefut az `ellenoriz` minden
   nyitott elemzésre.

## Nyitott kérdések

- Melyik beküldési mód lenne a kényelmesebb: Telegram, webes felület, vagy maradjon a parancssor?
- A horizontokat naptári időben számolom (például 3 hónap ≈ 63 kereskedési nap). A 15
  perces idősík a „következő kereskedési nap”, az 5 perces „8 óra nyitott piac”. Így jó?
- Ha a képre berajzolsz szinteket, azok mindig felülírják az automatikus tartományt,
  vagy csak jelöljem őket?
- Szeretnél egy olyan összesítő oldalt, ami a naplóból mutatja a találati arányt eszközönként és idősíkonként?
