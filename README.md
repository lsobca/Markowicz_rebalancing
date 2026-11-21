# Markowicz_rebalancing

Python výskumný projekt: ako frekvencia opakovaného odhadu Markowitzových váh
spolu s rebalansovaním ovplyvňuje výnos, riziko a náklady v rokoch 2011–2025.
Autoritatívna metodika a etapový postup sú v [AGENTS.md](AGENTS.md).

**Stav: etapa 8 — všetky dohodnuté zdrojové etapy vrátane offline testov sú napísané.
Žiadny analytický kód, downloader, test,
notebook, inštalácia závislostí, sťahovanie finančných dát ani backtest neboli
spustené. Konfigurácia a závislosti nie sú validačne overené. Výsledky neexistujú.**
Podrobnosti cache a manifestov sú v [proveniencii](data/provenance/README.md).
Moduly `src/universe.py`, `src/download_data.py`, `src/preprocessing.py`
a `src/optimization.py`, spolu s `src/backtest.py`, `src/metrics.py`
a `src/plotting.py`, zatiaľ neboli spustené
ani syntaxou či testami overené. Ani `run_analysis.py` a `analysis.ipynb`
neboli spustené. Workflow je implementovaný, jeho funkčnosť zatiaľ nebola overená.
Žiadny dashboard, web ani GUI nie sú súčasťou zadania.

## Budúce spustenie — až po samostatnom povolení

Z koreňa repozitára `Markowicz_rebalancing`, v prostredí Python 3.10 alebo
novšom (konkrétna kompatibilita neoverená), najprv pripravte závislosti:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Potom jediný príkaz vykoná sťahovanie, preprocessing, päť backtestov,
metriky, štyri grafy a generovanie záverov:

```sh
python run_analysis.py
```

Žiadny z týchto príkazov zatiaľ nebol vykonaný. Netreba ručne pripravovať CSV.
Predvolené výsledky idú do `results/`. Skript odmietne existujúce výstupné
súbory; ďalšiemu behu zvoľte nový adresár cez `--output`. Zachované `.gitkeep`
neprekážajú. Chyba skončí nenulovým exit kódom a stavom `failed` v manifeste;
prípadné čiastočné výstupy sa nesmú považovať za dokončený výsledok.

Citlivostné scenáre majú povinne oddelený adresár, napríklad:

```sh
python run_analysis.py --fee-rate 0 --output results_zero_fee
python run_analysis.py --rf-mode zero-sensitivity --output results_zero_rf
```

Tieto scenáre nenahrádzajú primárny beh. `--refresh` vyžiada novú dátovú
verziu; inak sa používa overená cache. Výstupný a cache priečinok sa riešia
voči priečinku zvoleného `--config` súboru. Historické režimy bez overeného
adaptéra stále explicitne zlyhajú, nikdy sa samy neprepnú na aktuálnu vzorku.

`analysis.ipynb` otvárajte z koreňa repozitára. Predvolene iba číta dokončené
výsledky a kontroluje ich SHA-256 podľa `run_manifest.json`. Bez výsledkov
skončí vysvetlením, nie sťahovaním. Voliteľná bunka s workflow má
`RUN_DOWNLOAD_AND_BACKTEST = False`; zmeniť ju treba až po osobitnom povolení.

Okrem ôsmich povinných CSV vzniknú `events.csv`, `schedule.csv`,
`drawdown_curves.csv` a `risk_free_alignment.csv`. `run_manifest.json`
obsahuje účinnú konfiguráciu, odkaz na dátový manifest, stav a SHA-256
výstupov. `conclusions.md` vznikne až po backteste a metrikách, s kvantifikáciou
výsledkov, podperiód, nákladov a koncentrácie aj povinnými obmedzeniami.
Notebook ani skript neinštalujú závislosti a nespúšťajú testy automaticky.

## Testy — zatiaľ iba zdrojové súbory

`tests/` obsahuje syntetické offline testy konfigurácie, účtovania, kalendára,
preprocessingu, optimalizátora, zdrojov a metrík vrátane podperiód.
Podrobnosti a hranice pokrytia sú v [tests/README.md](tests/README.md).
Po osobitnom povolení validácie je určený príkaz `python -m pytest tests`.
**Testy neboli spustené a ich úspešnosť sa netvrdí.** Implementačné etapy
sú týmto ukončené; sťahovanie, výpočty, testovanie a opravy na základe
ich výsledkov tvoria samostatne povoľovanú nasledujúcu fázu.

## Päť nezávislých portfólií

Všetky držia jednotlivé americké akcie, nie ETF, a začínajú rovnakými akciami,
váhami a externým kapitálom 10 000 USD pri uzatvorení 2011-01-03.

| Stratégia | Opätovný odhad váh a obchodovanie |
| --- | --- |
| Buy & Hold | Iba úvodný nákup; potom prirodzený drift |
| Mesačná | Koniec každého mesiaca |
| Štvrťročná | Koniec marca, júna, septembra a decembra |
| Polročná | Koniec júna a decembra |
| Ročná | Koniec decembra |

**Experiment súčasne mení frekvenciu odhadovania Markowitzových cieľových váh
aj vykonávania obchodov. Neizoluje čistý efekt frekvencie rebalansovania
k jednému nemennému vektoru cieľových váh.**

## Univerzum a hranice interpretácie

Predvolené `universe_mode: current_survivors_only` je **silne skreslená
ilustratívna vzorka dnešných členov indexu, ktorí prežili celé obdobie**.
Všetky súvisiace výsledky a grafy budú označené `illustrative survivors-only`.
Zdrojom bude aktuálna tabuľka S&P 500 na
[Wikipédii](https://en.wikipedia.org/wiki/List_of_S%26P_500_companies),
s dnešnými 11 GICS sektormi. Najprv sa získajú a overia ceny celého zoznamu;
vyžadujú sa kladné konečné upravené ceny pre každú očakávanú NYSE seansu
2005–2025, s nulovou toleranciou chýbajúcich cien po opakovaných pokusoch.
Až potom sa oprávnené symboly zoradia abecedne v sektoroch a vyberú
abecedným sektorovým round-robin postupom: najviac 10 na sektor a 100 celkom.
Posledné kolo môže byť neúplné; počty za sektory sa vykážu. Duplicitné
emitenty/triedy sa vylúčia a zaznamenajú. Výber nepoužíva budúci výnos,
ale úplné pokrytie do 2025 samo zavádza výrazný výber podľa budúceho prežitia.
Podmienka histórie od 2005 vylučuje neskoršie IPO.

Alternatívy sa nikdy nezapnú automaticky:

- `historical_top_cap_2010`: overené členstvo S&P 500, 10 vtedajších sektorov
  a kapitalizácia k 2010-12-31; 10 oprávnených emitentov na sektor podľa
  kapitalizácie, pri zhode podľa dobového permanentného identifikátora.
- `historical_roster_2010`: overený dobový zoznam a sektory; prvých 10
  oprávnených historických identifikátorov abecedne na sektor.

Oba historické režimy vyžadujú úplnú tréningovú históriu 2005–2010 a
zdokumentované korporátne udalosti vrátane delistingových výnosov/platieb.
Univerzum potom zostáva fixné okrem riadne modelovaných udalostí.
Dnešná kapitalizácia, členstvo ani sektor nesmú nahradiť hodnoty z roku 2010.
Kapitalizáciu možno odvodiť iba z dôveryhodnej dobovej ceny a dobového počtu
akcií s konzistentným ošetrením splitov. Bez overeného zdroja režimy skončia
jasnou chybou. Kandidátmi na posúdenie sú CRSP cez WRDS/univerzitu (vrátane
možnosti prístupu cez VŠB), Norgate alebo iný overený dodávateľ; dostupnosť
ani licencia neboli potvrdené. Samotné ceny Tiingo nedokazujú dobové členstvo
ani delistingové pokrytie. Yahoo nemožno považovať za úplný historický vesmír.

## Dáta a proveniencia

Budúci downloader bude automatický, bez požiadavky na ručne pripravené CSV.
`download_start: 2004-12-20` poskytne referenčnú cenu poslednej seansy 2004
pre prvý výnos 2005; táto cena nie je dodatočným tréningovým pozorovaním.
Yahoo koncový argument bude exkluzívny 2026-01-01. Použije sa
`yf.download(..., auto_adjust=False)` a stĺpec `Adj Close`, vrátane obsluhy
MultiIndex. Ide o spätne upravenú aproximáciu celkového výnosu s reinvestovaním
dividend; dividendy sa nepripočítajú druhýkrát. Ide o dátovú verziu ku dňu
stiahnutia, nie dobovo uložený zdroj. Špeciálne dividendy, fúzie a delistingy
môžu byť spracované nedokonale a historické hodnoty sa môžu spätne meniť.

Uložia sa pôvodné dáta, čas/URL zdroja, SHA-256, pôvodné a Yahoo symboly
(`BRK.B` → `BRK-B`), zoznamy pred/po filtrovaní, vylúčenia a príznaky
IPO/dostupnosti/delistingu. Sťahovanie bude mať User-Agent, validáciu schémy,
malé dávky, prestávky, exponenciálne opakovanie a cache podľa konfigurácie.
Chýbajúce ceny sa nedopĺňajú vpred ani vzad, nenahrádzajú nulou a nevyvolajú
fiktívny predaj. Neskorší výpadok vybranej akcie zastaví analýzu s chybou.

## Časovanie a účtovanie

Etapa 5 pridáva explicitné `run_backtest(data, stable_ids, config)`.
Vracia tabuľky hodnôt, úvodných váh, denných driftujúcich váh a pozícií,
obchodov, udalostí, optimalizačných diagnostík a kalendára. Nič automaticky
nespúšťa ani neexportuje. Úvodná alokácia aj exekúcia sa vypočítajú raz
a rovnako použijú pre všetkých päť samostatných účtov.
Naplánované rebalansovania sa v kumulatívnych počtoch počítajú podľa
exekúcií vo vzorke; posledné signály s exekúciou až v roku 2026 sú zachované
v kalendári ako nevykonané a nezvyšujú tieto počty.

Pozície sú zlomkové jednotky upraveného total-return cenového proxy,
nie rekonštrukcia právnych počtov akcií a dividendových peňažných tokov.
Zvyšková numerická hotovosť zostáva nezáporná a nenesie úrok.
Bisection používa finančne realizovateľnú dolnú hranicu; poplatky sa
počítajú zo skutočných reprezentovateľných zmien pozícií. Každý nenulový
obchod sa započíta, bez minimálneho príkazu. Kontrola účtovnej rovnosti
má absolútnu toleranciu 1e-8 USD; zlyhanie zastaví výpočet.

Signál vzniká pri close poslednej skutočnej seansy obdobia, iba z dovtedy
známych dát. Obchod sa vykoná pri close nasledujúcej seansy a ovplyvní až
ďalšie výnosy. Použije sa explicitne ohraničený kalendár
`xcals.get_calendar("XNYS", start="2004-12-01", end="2026-12-31")`.
Po neskoršom povolení testov treba overiť aj Sandy 2012-10-29/30, Bush
2018-12-05 a Carter 2025-01-09. Predpokladané prvé páry signál → obchod:
mesačne 2011-01-31 → 02-01, štvrťročne 03-31 → 04-01, polročne
06-30 → 07-01, ročne 2011-12-30 → 2012-01-03. Kalendár zatiaľ nebol overený.
Po úvodnom nákupe sa okamžite nereoptimalizuje. Obchody po poslednej seanse
2025 sa nevykonajú; posledný decembrový ročný signál už nemá obchod vo vzorke.

Poplatok je 0,1 % každého nákupného aj predajného nominálu, vrátane úvodného
nákupu vo všetkých portfóliách. Úvodný investovaný nominál je `10000 / 1.001`.
Zlomkové akcie sú zámerne povolené, hotovosť nesmie byť záporná. Pri
rebalansovaní sa vyrieši `X = V - c * sum(abs(w_i * X - h_i))`, kde `V`
zahŕňa hotovosť a `h_i` sú aktuálne akciové nominály, s absolútnou toleranciou
1e-8 USD. Akcie sa upravia na cieľ `w_i * X`; zostatok, pozície a poplatky
sa musia účtovne zosúladiť. Bez obchodov nie je poplatok.

Obrat je **hrubý obojstranný obrat**: súčet absolútnych nákupných/predajných
nominálov delený hodnotou pred obchodom, sčítaný cez exekúcie. Úvodný nákup
sa vykazuje oddelene. Naplánované udalosti, udalosti s akýmkoľvek kladným
obchodom a materiálne rebalansovania sa počítajú osobitne. Materiálna udalosť
má post-initial obrat striktne `> 0.0001`; nejde o minimálnu veľkosť príkazu.
Aj drobné obchody patria do účtovania, obratu a poplatkov. Samostatný override
`fee_rate: 0` bude slúžiť iba ako označená citlivostná analýza.

## Odhady, bezriziková sadzba a optimalizácia

Etapa 4 pridáva `optimize_signal(data, signal_date, stable_ids, config, initial=False)`.
Vracia váhy, odhady priemeru, pôvodnú aj regularizovanú kovarianciu a diagnostiku
jedného signálu; nevykonáva obchody. Pre úvodný signál sa zadá `initial=True`.
Identifikátory musia byť jedinečné a zarovnané s aktívami; v aktuálnej vzorke
možno použiť konzistentne zachované pôvodné symboly, nie tvrdené dobové ID.
Výstup zahŕňa hranice okna, dátumy dostupnosti sadzby, zásah do vlastných čísel,
stav solvera, odfiltrovanú váhu a koncentráciu. `summarize_concentration`
pripraví počty, priemery, minimá a maximá diagnostík jednej stratégie.
Po váhovom filtri a normalizácii sa negarantuje zachovanie pôvodného optima.

Pri následných oknách sa najprv vyberú iba ceny striktne po ľavej hranici;
prvá ponechaná cena slúži ako referencia a výnosy začínajú až ďalšou seansou.
Nevyužíva sa teda cena z vylúčenej hranice. Výnimkou je úvodné obdobie,
kde sa posledná cena 2004 zámerne použije pre prvý výnos 2005.

Etapa 3 pridáva `prepare_data(bundle, config)`: v pamäti opätovne overí všetky
vybrané akcie, zarovná ich na explicitný XNYS kalendár, ponechá referenčnú
cenu poslednej seansy 2004 a vypočíta jednoduché výnosy od prvej seansy 2005.
Ceny sa nikdy nedopĺňajú. Neplatná vybraná akcia vyvolá `PriceValidationError`
s tabuľkou `.report`; nevyraďuje sa potichu. Report obsahuje pokrytie
2005–2010 a 2011–2025, chýbajúce/neplatné ceny a referenčnú seansu.
Pomocné funkcie poskytujú ročný aritmetický priemer, výberovú kovarianciu,
volatilitu a denné excess výnosy. Výber tréningových okien patrí do etapy 4.
Žiadny report ani výstupný súbor zatiaľ nevznikol.

Zarovnanie FRED uchováva dátum pozorovania, predpokladanej dostupnosti
a vek sadzby. Dátum dostupnosti je dátum pozorovania plus jeden pracovný
deň podľa USFederalHolidayCalendar; nasleduje iba spätné časové priradenie.
Denná sadzba je označená seansou, na ktorej končí príslušný denný výnos.
Ak pre prvú seansu neexistuje skoršia dostupná sadzba, spracovanie zlyhá.
Ide o stanovený predpoklad publikačného oneskorenia, nie o overené historické
časy zverejnenia; aktuálne stiahnutá verzia FRED nie je historický archív revízií.

Úvodné tréningové obdobie je 2005–2010 vrátane (šesť rokov), ďalšie okná
sú presne päť kalendárnych rokov: pre signál D platí
`D - DateOffset(years=5) < date <= D`. Napríklad 2011-01-31 zahŕňa ceny
od 2006-02-01. Asymetria šesť/päť rokov je zámerná a ovplyvňuje porovnateľnosť.
Denné výnosy sú jednoduché; ročný priemer = denný aritmetický priemer × 252,
ročná výberová kovariancia = denná kovariancia × 252, `ddof=1`.

Predvolená sadzba je [FRED DGS3MO](https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO),
sťahovaná bez API kľúča: anualizovaný výnos 3-mesačného Treasury s konštantnou
splatnosťou, nie realizovateľný výnos investície do pokladničnej poukážky.
Percentá sa delia 100. Pozorovanie je dostupné najskôr o jeden americký
pracovný deň neskôr (USFederalHolidayCalendar); signál používa poslednú
už dostupnú hodnotu. Povolené je len dopĺňanie z minulosti, nikdy z budúcnosti.
Ex-post Sharpe používa zarovnané denné excess výnosy s transformáciou
`(1 + annual_rate)**(1/252) - 1`. Pri výpadku zdroja bez overenej cache sa
výpočet zastaví; budúci `--rf-mode zero-sensitivity` bude výslovne označená
citlivosť, nikdy tichá náhrada.

Pre aspoň jedno `mu_i > rf` sa použije cvxpy s explicitne zvoleným solverom
CLARABEL: minimalizácia `x' Sigma x`, obmedzenia `(mu-rf)'x = 1`, `x >= 0`,
potom `w = x / sum(x)`. Kovariancia sa symetrizuje, skontrolujú sa vlastné
čísla a transparentne regularizuje na nakonfigurovanú kladnú dolnú hranicu;
samotné `psd_wrap` neopravuje maticu. Overia sa konečnosť, obmedzenia a cieľ.
Váhy striktne `< 0.0001` sa vynulujú, zvyšok normalizuje. Bez shortovania,
bez maximálneho váhového limitu, plne investované portfólio.

Ak všetky excess odhady sú nekladné, núdzové pravidlo investuje 100 % do
akcie s najväčším `mu_i-rf`, pri zhode do lexikograficky prvého stabilného ID;
zaznamená `nonpositive_excess_fallback`. Toto **nie je garantované maximum
Sharpe pre záporné excess výnosy**. Nulová/neplatná volatilita vybranej akcie
alebo iné zlyhanie solvera znamená chybu, nikdy tichú náhradu rovnakými váhami.
Počiatočné a všetky ďalšie signály vykážu počet pozícií, najväčšiu váhu a
HHI = sum(weight²), aj časové súhrny. Nestabilné odhady priemerov, šum a
neobmedzené váhy môžu viesť k extrémnej koncentrácii, najmä mesačne.

## Budúce výsledky a interpretácia

Etapa 6 pridáva `calculate_metrics(result, risk_free, config)` a samostatné
funkcie `plot_growth`, `plot_risk_return`, `plot_drawdowns`, `plot_weight_evolution`.
Export je výlučne explicitný cez `export_metrics` a `export_figures`; tieto
funkcie zatiaľ neboli spustené a neexistujú výsledné CSV ani obrázky.
CSV používa UTF-8, ISO dátumy, desatinné zlomky pre výnosy a prázdne polia
pre nedefinované metriky. Realizovaný Sharpe je priemer denných excess výnosov
delený ich výberovou smerodajnou odchýlkou, krát sqrt(252); nulový menovateľ
znamená nedefinovanú hodnotu s explicitným stavom. Maximálny drawdown v tabuľke
je kladná veľkosť straty, zatiaľ čo grafické krivky sú nekladné.

Koncentrácia sa sumarizuje osobitne z denných skutočných váh a zo signálových
cieľov. Podperióda bez signálu má prázdne signálové súhrny, nie fiktívny signál.
Graf riziko/výnos porovnáva anualizovanú volatilitu s čistým CAGR. Graf váh
používa spoločný výber najvýznamnejších akcií podľa priemernej pozorovanej
váhy v celom období; toto spätné poradie slúži iba na zobrazenie, nikdy na
výber investičného univerza. Zvyšok tvorí „Other“, hotovosť je samostatná.
Všetky grafy uvádzajú survivors-only označenie, poplatok a režim sadzby.

Povinné metriky: konečná hodnota, celkový čistý výnos, CAGR, anualizovaná
volatilita, realizovaný Sharpe, maximálny drawdown, tri počty udalostí,
hrubý obojstranný obrat, celkové poplatky a koncentrácia. Čistý výnos a CAGR
vychádzajú z externých 10 000 USD a zahŕňajú úvodný poplatok. CAGR má pôvod
v close 2011-01-03 a exponent podľa skutočných dní / 365,25. Volatilita je
`std(daily_simple_return, ddof=1) * sqrt(252)` bez fiktívneho denného trhového
výnosu pre úvodný poplatok. Celkový drawdown má úvodné maximum 10 000 USD.

Povinné podperiódy: 2011–2015 od externých 10 000 USD pred prvým nákupom;
2016–2020 od close 2015-12-31; 2021–2025 od close 2020-12-31. Hodnoty na
konci predchádzajúceho roka sú základom pomerov, rizika aj drawdownu neskorších
podperiód, nie prvá hodnota už po januárových obchodoch.

Budúce CSV v `results/`: `portfolio_metrics`, `portfolio_values`,
`initial_weights`, `weight_history`, `trades`, `optimization_log`,
`data_quality_report`, `subperiod_metrics`. Štyri statické PNG v
`results/graphs/`: `portfolio_growth`, `risk_return`, `drawdowns`,
`weight_evolution`; zobrazia všetkých päť portfólií. Vývoj váh oddelí
najvýznamnejšie akcie a zvyšok zoskupí ako „Other“. Zatiaľ sú adresáre prázdne.
`results/conclusions.md` vznikne až z reálnych výsledkov povoleného behu:
odlíši konečnú hodnotu, rizikovo upravený výnos, drawdown, náklady/obrat,
koncentráciu a zmeny medzi podperiódami, bez vymyslených víťazov.

Poplatok nezahŕňa spread, sklz, trhový dopad, financovanie ani dane z dividend
či realizovaných ziskov; náklady preto môžu byť podhodnotené. Dane sa
nemodelujú. Jedna historická trajektória nepreukazuje štatisticky významnú
prevahu. Závery musia uviesť survivorship bias, obmedzenie IPO/tréningovej
histórie, spätné dátové verzie, odhadové riziko a neistotu realizovanej cesty.
Benchmarky sú predvolene vynechané; porovnávajú sa iba uvedené stratégie,
nie schopnosť Markowitza prekonať široký trh. SPY total-return proxy alebo
1/N možno pridať iba po osobitnom súhlase a mimo súťaže piatich portfólií.

## Súbory a ďalší postup

`config.yaml` obsahuje metodické predvoľby a explicitné technické tolerancie,
limity pokusov a grafické nastavenia. `requirements.txt` používa ohraničené
rozsahy, vrátane `exchange_calendars>=4.7,<5`; kompatibilita nebola overená.
CLARABEL je pevne zvolený solver, verzia balíka má ohraničený rozsah namiesto
neovereného presného pinu. `src/__init__.py` je prázdny. Surové cenové dáta,
spracované dátové cache a tajné premenné prostredia sa necommitujú.
Celý `results/` vrátane CSV, záverov a grafov sa môže commitovať.
Pre reprodukovateľnosť sa commitujú aj záznamy v `data/universe/`
(zoznamy a vylúčenia), `data/manifests/` a `data/provenance/`
(zdroje, dátumy stiahnutia a kontrolné súčty). Budúce moduly majú tieto
záznamy ukladať do uvedených adresárov. Zatiaľ existuje iba dokumentácia
a prázdna šablóna proveniencie, nie skutočné zdrojové záznamy.
Ďalšie etapy sa ukladajú priamo na vetvu `main` podľa pokynu používateľa.

[Etapový plán](PROJECT_PHASES.md): kostra → zdroje a sťahovanie → čistenie →
optimalizácia → backtest → metriky/grafy → orchestrácia/notebook → zdrojové
testy. Po každej etape nasleduje commit a súhlas s ďalšou. Inštalácia,
sťahovanie, výpočty aj validácia vyžadujú neskoršie samostatné povolenie.
