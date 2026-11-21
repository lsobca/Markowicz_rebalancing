# Proveniencia — etapa 2

Tento adresár obsahuje iba šablónu, nie záznamy uskutočneného sťahovania.
Downloader ani kontroly neboli spustené. Historický zdroj nebol overený.

Budúce explicitné volanie `download_inputs(config, root, refresh=False)`:

- uloží manifest do `data/manifests/<run_id>.json`, vrátane stavu zlyhania;
- uloží zoznam pred výberom, dostupnosť všetkých kandidátov, zoznam po výbere,
  audit, vylúčenia a počty sektorov do `data/universe/<run_id>/`;
- uloží nezmenené HTTP odpovede a tabuľky vrátené yfinance do ignorovanej
  cache `data/raw/objects/<sha256>`; pri Yahoo ide o serializáciu odpovede
  knižnice, nie zachytenie pôvodných HTTP bytov poskytovateľa;
- uloží samostatné cenové série a cache index podľa parametrov požiadavky;
- zaznamená skutočné časy získania, kontrolné súčty, konfiguráciu, verzie
  balíkov, opakované použitie cache a chyby. Pri obnovení neprepíše staré
  obsahovo adresované objekty ani nespojí ceny z rôznych verzií do jednej série.

Cache sa používa len po zhode požiadavky, SHA-256 a schémy; neúplné Yahoo
histórie sa opakujú samostatne aj po dávkovom pokuse. `refresh=True` žiada
nové dáta; po zlyhaní môže použiť overenú úplnú cache, čo sa vykáže.
Manifest sám nenahrádza archivované surové dáta. Pre presnú reprodukciu
konkrétnej dátovej verzie treba odovzdať aj zodpovedajúce raw objekty mimo
Gitu v súlade s licenciou poskytovateľa. Nové stiahnutie môže priniesť inú verziu.

`ipo_status` a `delisting_status` zostávajú `unknown_not_verified`:
krátka história ani dátum zaradenia do indexu nie sú dôkaz IPO/delistingu.
Osobitné príznaky označujú neskorý začiatok a skorý koniec dostupnosti.
Wikipedia CIK sa používa na odstránenie duplicitných aktuálnych emitentov;
nie je vydávaný za historický identifikátor konkrétnej akcie. Pri viacerých
oprávnených triedach sa ponechá abecedne prvý pôvodný symbol.

Historické režimy skončia chybou pred sieťovým volaním. Ich implementácia
vyžaduje overený dobový zdroj, nie iba vyplnenie konfiguračnej cesty.
FRED zostáva v pôvodných ročných percentách: lag, zarovnanie a denné výnosy
patria do etapy 3. Nie je tu optimizer, backtest ani generovanie výsledkov.
