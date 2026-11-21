# Závery z uskutočneného behu

Režim: **current_survivors_only — illustrative survivors-only**.
Poplatok: 0.10%; RF: fred_dgs3mo.
Dátový manifest: `20261121T181651Z-0d395a84`.

Experiment súčasne mení frekvenciu odhadovania Markowitzových cieľových váh aj obchodovania. Neizoluje rebalansovanie k jednému fixnému vektoru váh.

## Celkové výsledky

- Najvyššia konečná hodnota (USD): buy_and_hold: 199,518.4698.
- Najvyšší realizovaný Sharpe: quarterly: 0.9912.
- Najmenší maximálny drawdown: monthly: 29.19%.
- Najnižšie celkové poplatky (USD): buy_and_hold: 9.9900.
- Najnižší post-initial hrubý obojstranný obrat: buy_and_hold: 0.0000.

Obrat je súčet pomerov nominálov k hodnote účtu, nie anualizované percento.

| Stratégia | Čistý výnos | CAGR | Volatilita | Poplatky USD | Post-initial obrat |
| --- | ---: | ---: | ---: | ---: | ---: |
| buy_and_hold | 1895.18% | 22.10% | 23.42% | 9.99 | 0.0000 |
| monthly | 1344.00% | 19.49% | 18.96% | 3126.26 | 54.0733 |
| quarterly | 1490.58% | 20.27% | 18.99% | 1946.44 | 30.0599 |
| semiannual | 1486.05% | 20.24% | 19.15% | 1220.78 | 18.8951 |
| annual | 1243.01% | 18.92% | 19.31% | 710.84 | 12.3869 |

## Podperiódy

2011–2015 začína externými 10 000 USD pred úvodným nákupom; 2016–2020 od close 2015-12-31 a 2021–2025 od close 2020-12-31.

**2011-2015**: najvyšší čistý výnos: semiannual: 223.26%; najvyšší Sharpe: semiannual: 1.4018; najmenší drawdown: semiannual: 15.23%.

**2016-2020**: najvyšší čistý výnos: buy_and_hold: 249.26%; najvyšší Sharpe: buy_and_hold: 1.0745; najmenší drawdown: monthly: 29.01%.

**2021-2025**: najvyšší čistý výnos: monthly: 107.38%; najvyšší Sharpe: monthly: 0.6853; najmenší drawdown: semiannual: 29.01%.

Poradie lídrov podľa čistého výnosu sa medzi podperiódami menilo.

## Koncentrácia a odhady

| Stratégia | Priemerný denný počet pozícií | Najvyššia denná váha | Priemerný denný HHI | Max. signálový HHI |
| --- | ---: | ---: | ---: | ---: |
| buy_and_hold | 7.00 | 52.29% | 0.2699 | 0.2146 |
| monthly | 12.09 | 39.01% | 0.1450 | 0.2336 |
| quarterly | 12.04 | 39.04% | 0.1459 | 0.2196 |
| semiannual | 11.84 | 39.04% | 0.1473 | 0.2196 |
| annual | 11.60 | 38.35% | 0.1513 | 0.2196 |

Záznamy signálov s núdzovým pravidlom: 0; s orezaním vlastných čísel kovariancie: 0. Počty sú po stratégiách, vrátane spoločného úvodného odhadu a záverečných signálov bez exekúcie.
Núdzové pravidlo nie je garantovaným maximom Sharpe pri nekladných excess výnosoch. Nestabilné priemery a šum bez limitu maximálnej váhy môžu viesť ku koncentrácii, najmä pri mesačnom preodhadovaní. Úvodné šesťročné a ďalšie päťročné okná sú zámerne asymetrické a obmedzujú porovnateľnosť.

## Zdroje a obmedzenia

- Yahoo Finance / yfinance: získané od 2026-11-21T18:06:39.816883+00:00 do 2026-11-21T18:27:34.769027+00:00.
- https://en.wikipedia.org/wiki/List_of_S%26P_500_companies: získané od 2026-11-21T18:06:37.016949+00:00 do 2026-11-21T18:06:37.016949+00:00.
- https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO: získané od 2026-11-21T18:27:38.744616+00:00 do 2026-11-21T18:27:38.744616+00:00.
Úplné URL, jednotlivé dátové verzie a SHA-256 sú v uvedenom dátovom manifeste.

Vzorka je silne skreslená dnešným členstvom a dostupnosťou až do 2025 (survivorship a look-ahead selection bias). Podmienka histórie od 2005 vylučuje neskoršie IPO. Časovanie signálov bez budúcich výnosov toto výberové skreslenie neodstraňuje.
Yahoo Adj Close je retrieval-date verzia spätne upraveného total-return proxy, nie dobový archív. Korporátne udalosti, delistingy a revízie môžu byť neúplné. FRED používa predpoklad jedného amerického pracovného dňa oneskorenia, nie overené historické release timestamps. DGS3MO je výnosová sadzba, nie investovateľný realizovaný výnos.
Modelovaný poplatok nezahŕňa spread, sklz, trhový dopad ani financovanie. Dane z dividend a realizovaných ziskov sa nemodelujú; celkové náklady môžu byť podhodnotené.
Jedna realizovaná trajektória 2011–2025 nepreukazuje štatistickú významnosť ani budúcu prevahu. Porovnanie je opisné, bez inferenčného testu. Benchmark je vynechaný: závery porovnávajú päť stratégií, netvrdia prevahu nad širokým trhom.
