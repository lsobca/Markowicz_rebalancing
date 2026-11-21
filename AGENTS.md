# AGENTS.md — Markowitz portfolio optimization and rebalancing backtest

## Mandatory phased workflow for Codex — user approval after EVERY phase

**This section takes precedence over any instructions elsewhere in this file about implementing, downloading, installing, testing, executing or completing the entire project in one go.** The user wants incremental coding and saving, **not automatic validation**.

### Working protocol

1. **Start with Phase 1 ONLY.** Do not create code/files belonging to later phases, even if they are trivial.
2. For each authorized phase: read the existing repository, add/edit **only that phase's files**, save/commit the completed changes to GitHub on the working branch, and stop.
3. **Do not run scripts, unit tests, notebooks, linters, dependency installation, data downloaders or backtests. Optional exception: `python -m py_compile` on written Python files solely for syntax; no imports, tests, execution or downloads. Disclose whether done. Do not claim correctness.** Write coherent code and tests (in their allocated phase), but **do not execute them**. Git operations needed solely to inspect and save files are fine. Do not claim any unexecuted code works.
4. After saving the phase, respond briefly **in Slovak** with (a) phase number and completed files, (b) commit reference/link if available, (c) what comes next and (d) the explicit question **"Mám pokračovať ďalšou etapou?"**. **STOP and await an affirmative user response.** Never advance to the next phase without confirmation. A request to modify the current phase is not permission to start another one.
5. If a phase cannot be completed due to missing data, access or permissions, commit whatever useful source/documentation can be saved, disclose the blocker, and ask whether to continue or adjust that phase. No fabricated data or figures.
6. Full-download and computation requirements below describe the **end goal and functionality to implement**, not permission to run the workflow. Data must eventually be downloadable automatically by a single scripted command, but while following this phased workflow **write the download code without executing it**. Only a subsequent explicit user request can authorize downloads/runs.
7. Keep the approved quantitative-finance methodology in this document unchanged unless the user specifically authorizes a modification. Do not create a dashboard.

### Phase 1 — Skeleton and configuration ONLY

Create/update `README.md` (scope, 5 strategies, roadmap, all agreed assumptions, disclaimer that nothing has been run), `config.yaml` (all binding numeric defaults, date window, fee/timing/risk-free settings), `requirements.txt`, `.gitignore`, empty Python package `src/__init__.py` and necessary empty directory placeholders. A concise `PROJECT_PHASES.md` is allowed. **No download, optimizer, backtest, plots, or tests yet.** Commit and ask for approval.

### Phase 2 — Historical universe and download infrastructure

Implement `src/universe.py` and `src/download_data.py` plus provenance templates. Implement historical point-in-time tiers ONLY with a verified source; otherwise fail clearly for that mode. Implement the expected runnable, explicitly biased current-constituent survivors-only tier as described below. Code should download stock universe, stock prices and FRED DGS3MO **when run later**, implement the documented 2010 historical-vs-survivors-only selection tiers, availability/IPO/delisting flags, caching and retries. No downloads or real API calls now; no actual results or invented source records. Commit and ask.

### Phase 3 — Cleaning and returns

Implement `src/preprocessing.py`: adjusted-price validation with zero tolerated missing trading-session prices in the baseline, 2011–2025 full-coverage flags, synchronized dates, returns, annualization, and quality reports. Explicitly implement FRED DGS3MO one-US-business-day publication lag and past-only forward-fill; no future backfill or price forward-fill. No data execution. Commit and ask.

### Phase 4 — Markowitz optimizer

Implement `src/optimization.py` with PSD-regularized CLARABEL positive-excess convex formulation, documented all-nonpositive-excess contingency, lagged risk-free input, exact five-year rolling/initial six-year windows, strict 0.0001 stock-weight filter, normalization and concentration diagnostics. **Do not yet build the backtest.** Commit and ask.

### Phase 5 — Five-strategy backtest engine

Implement `src/backtest.py`: all five strategies, period-end signal / next-close execution, initial fee, post-fee wealth equation solver, shares and nonnegative cash, drift, gross turnover and material-event threshold; outputs only upon future run. Commit and ask.

### Phase 6 — Metrics and static charts

Implement `src/metrics.py` and `src/plotting.py`: return/risk/fees/turnover/concentration metrics; explicit 2011–15/2016–20/2021–25 starting baselines described below; four static chart functions and export formatting. No run, no invented completed chart or result CSV. Commit and ask.

### Phase 7 — Orchestration, notebook and interpretation templates

Implement `run_analysis.py` and `analysis.ipynb`, finish `README.md` with **one-command** future downloads + processing + backtest, explain how the run will populate `results/`. Create a **template/generator** for `results/conclusions.md` which will derive quantitative conclusions from results **only when a run is later authorized and actually executed**. Do not write fake numerical results, and do not invoke the command or notebook. Optional benchmark code is outside core scope and should be skipped unless the user explicitly requests it. Commit and ask.

### Phase 8 — Offline test source files ONLY

Write `tests/` with synthetic fixtures and tests for the critical methodology in this AGENTS.md, including timing, fees, strict thresholds, convex optimizer, nonpositive-excess contingency, data-vintage/corporate-action failures, rolling windows, no-look-ahead and metrics. **Save tests without running them**; do not install or invoke pytest. Commit and ask.

### After Phase 8

**Stop.** Report that all agreed code phases are saved but **not executed or validated**, that no real financial data or results have been downloaded/generated, and ask whether the user wants to **separately authorize** a later data-download and execution/validation stage. Never automatically proceed to that stage.

---

## Mission

Implement a reproducible, academically defensible **Python quantitative-finance research project** investigating:

> How does the frequency of repeatedly re-optimizing and rebalancing a US-equity portfolio with Markowitz mean–variance optimization affect its performance, risk, and trading costs over 2011–2025?

**Build the project, not merely a proposal. Download all necessary legitimate historical data yourself.** Do not ask the user to manually prepare stock-price CSVs. If important historical data cannot be sourced correctly, implement a documented fallback and explicitly disclose limitations; never fabricate or silently replace missing data.

**No dashboard, Streamlit, website, or GUI.** Produce a runnable Python workflow, Jupyter notebook for analysis, CSV outputs, static charts, and concise conclusions.

## Binding implementation specification — revised 2026-11-21

**This section is mandatory and must be reflected in `config.yaml`, README, code and tests.** Do not offer multiple equally default conventions.

### Timeline and accounting (fixed)

- Set `initial_capital_usd: 10000`, `fee_rate: 0.001`, `initial_purchase_fee: true`, `initial_fee_policy: charge_all_portfolios`, `signal_convention: period_last_session_close`, `execution_convention: next_session_close`, `material_rebalance_turnover_threshold: 0.0001`, `weight_filter_threshold: 0.0001` in config.
- **Charge the 0.1% trading fee on gross executed notional for every buy and sell, including the initial allocation for all five portfolios and Buy & Hold.** Purchase notional is funded from $10,000 less its fee (invest 10000/1.001, not 10000 and then borrow the fee). Keep cash nonnegative; every strategy receives identical starting conditions. Count/reconcile fees and gross turnover; distinguish initial purchases from subsequent rebalancing.
- **Signal at the close of the last actual trading session of the relevant calendar period; estimate exclusively from data through that completed close; execute at the close of the NEXT trading session**, so the freshly estimated allocation affects only subsequent returns. Initial training ends with the last 2010 session (2010-12-31), and initial allocation executes at the first 2011 session close (2011-01-03). All portfolios share this execution/valuation basis. No trades after the final 2025 session. The late-December-2025 annual signal therefore has no within-sample execution.
- Signals: monthly = last trading session of every month; quarterly = last trading session of March/June/September/December; semiannual = last trading session of June/December; annual = last trading session of December. First 2011 signals and trades: monthly Jan 31 -> Feb 1, quarterly Mar 31 -> Apr 1, semiannual Jun 30 -> Jul 1, annual Dec 30 -> Jan 3 2012 (subject to verified actual NYSE calendar). **No immediate re-optimization after initial purchase in January 2011.**
- **Material rebalance event for reporting**: a *post-initial* executed rebalance date with `gross_notional / pre_trade_wealth > 0.0001` (strictly greater than 0.01% of pre-trade value). This is NOT a minimum order size: include all positive executions in fees, gross turnover and bookkeeping, even if smaller. Report scheduled events, events with any positive trading, and material rebalance count separately. Keep this distinct from the 0.0001 *stock-weight* filter.
- **Turnover**: sum over execution dates of `sum(abs(executed buy/sell notionals))/portfolio_value_before_orders`; label this **gross two-sided turnover**. Report post-initial turnover separately from initial purchases, to avoid penalizing all portfolios equally in comparisons.

### Universe / source (fixed, with clearly labeled feasibility fallback)

- The desired **unbiased historical experiment** needs contemporaneous security identities, a 2010-12-31 constituent roster and market caps, adjusted total returns, and reliable returns/cash proceeds for delistings. **yfinance cannot be relied on to provide a complete delisted equity universe; its ordinary free-data run is expected to be survivors-only and biased**, not a rare edge case. Document possibility of CRSP through WRDS/university access (including VŠB), Norgate, and assessed vendors. Tiingo prices alone do not prove point-in-time universe or delisting coverage. Do not fabricate either.
- **Primary historical universe construction rule**: source *documented 2010-12-31 S&P 500 membership, GICS sector as of 2010 and 2010-12-31 market capitalization*. Within each of the **10 sectors at that date** select **top 10 eligible common-stock issuers by 2010-12-31 market capitalization per sector**, target 100, remove duplicate issuers/share classes; ties deterministically by contemporaneous permanent identifier. Retrieve cap from a verified dated archive/vendor or compute only from trustworthy 2010 price and historical shares outstanding, consistently adjusted for share splits. **Never substitute today's market cap, membership or sector assignments as 2010 data.** Exclude and log assets with no complete 2005–2010 estimation history. This deliberately excludes post-2005 IPOs: report IPO/history eligibility bias. Keep the original universe fixed thereafter except for properly modeled corporate events.
- **Executable free-data baseline**, expected when dated reliable constituents/caps/delistings are not available: (1) try the historical top-10-per-sector rule; (2) if dated 2010 membership and sectors exist but historic caps do not, take the first 10 by stable historical identifier alphabetically per 2010 sector, then use accessible prices, recording every missing/delisted company; (3) if no documented 2010 snapshot exists, use a sourced current S&P 500 list, at most 10 tickers alphabetically per each of today's 11 GICS sectors, with global maximum 100, selecting in deterministic alphabetical sector round-robin order, and requiring complete 2005–2025 history in this explicitly biased baseline, no future-performance selection, then document all excluded tickers. **Label tiers (2) and (3) prominently "illustrative survivors-only", and tier (3) "strongly biased current-constituent convenience sample".** Persist the unfiltered candidate roster, selection and exclusions; never imply that these samples are historical top-cap 2010 universes. Auto-download and cache reproducibly; do not require hand-prepared CSVs.
- Pin a specific `yfinance` version in requirements; call `yf.download(..., auto_adjust=False)` and use `Adj Close` (explicitly handle MultiIndex; `auto_adjust=True` may remove `Adj Close`). Use vendor `Adj Close` as a **backward adjusted total-return proxy**, incorporating splits and assuming reinvestment of dividends, never counting dividends a second time. The adjustment reflects the **data vendor's retrieval-date vintage**, not a contemporaneously saved 2010 feed; save as-downloaded data, download timestamp, source and checksum; warn of vintage changes and possible imperfect treatment of special dividends, mergers and delistings. Never replace missing/delisted observations by zeros or unlimited forward-fill.

### Risk-free inputs and optimization (fixed)

- Default `rf_mode: fred_dgs3mo`: auto-download **FRED DGS3MO**, the annualized yield on a 3-month constant-maturity US Treasury (risk-free proxy, **not** investable realized Treasury-bill returns). Fetch from `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO` without API key. At signals use the latest **previously published** value, lagged at least one US business day; only forward-fill from past rates over non-observation days, never backfill from the future. Convert percent to decimal and use annual-rate units against annualized mean/covariance. For ex-post Sharpe use aligned daily excess returns and a documented daily-rate transformation (e.g. `(1+annual_rate)**(1/252)-1`), no interpolation from future observations. If FRED download fails and no validated cached copy exists, fail explicitly for primary runs; allow `--rf-mode zero-sensitivity` ONLY as prominently labeled 0% sensitivity, never as a silent default. Report FRED provenance and availability.
- Default optimizer when at least one stock has `mu_i > rf`: **positive-excess max-Sharpe convex transformation** `min_x x' Sigma x`, subject to `(mu-rf)'x = 1`, `x >= 0`, then `w=x/sum(x)`. Use cvxpy with pinned CLARABEL solver; symmetrize covariance, check eigenvalues and transparently regularize/clip non-PSD eigenvalues before solving (`psd_wrap` alone is not a repair). Verify finite solution, constraints and objective and then apply the fixed post-optimization weight filter `w < 0.0001` -> zero, normalize. No shorting, no extra weight cap. Handle singular covariance explicitly (regularize only transparently); do not silently substitute equal weights.
- **If no expected stock return exceeds rf** (no positive excess expected return), the convex positive-excess constraint is infeasible. Use deterministic disclosed emergency contingency: **100% in the stock with largest `mu_i-rf`** (tie: lexicographically smallest stable ID), record `optimizer_status=nonpositive_excess_fallback` and warn this is **not mathematically the guaranteed max-Sharpe solution for all-negative excess-return cases**; no arbitrary equal-weight fallback. If chosen asset volatility is zero/invalid, halt with an explicit error. If other solver failures occur, halt/report instead of fabricating a portfolio.
- Initial training window **2005–2010 inclusive = six calendar years**; every later window = trailing **five calendar years**, intentionally asymmetric per user request. Explain its effect on comparability in README and conclusions.
- **Mandatory concentration reporting**: holdings count, largest holding share, HHI = sum(weight^2) at initial and all later signal dates, with summary statistics across time. Discuss unstable mean estimates, noise and potential concentration caused by no cap, especially monthly re-optimization.

### Interpretation and statistical caution (fixed)

- 0.1% modeled fee excludes bid/ask spread, slippage, market impact, financing, and taxes on dividends/realized gains. Explicitly state the cost estimate may be understated, and **no taxes are modeled**.
- Alongside 2011–2025 overall metrics, **report the fixed subperiods 2011–2015, 2016–2020 and 2021–2025**, with clearly defined start-of-subperiod valuation and risk calculations. A single observed market path does **not** establish statistical significance; do not claim statistically reliable superiority without an appropriate inference procedure.
- **Optional benchmark, not part of the five-portfolio competition:** add a separately labeled S&P 500 total-return proxy (e.g. SPY adjusted close with assumptions) **only if downloads are reliable and it's clearly separated from individual-stock candidate universe**. Also an equal-weight 1/N strategy is optional, with the same universe, fees and timing. Benchmarks do not substitute for any of the five user-requested portfolios. If benchmarks are omitted, explain that comparative claims concern the five strategies, not whether Markowitz beats the broad market.
- For subperiod performance, 2011–2015 begins with initial external $10,000 immediately before the 2011-01-03 first purchase (including its fee); 2016–2020 begins at 2015-12-31 closing account wealth, and 2021–2025 at 2020-12-31 closing account wealth; subsequent subperiod wealth ratios use these opening marks, and risk/drawdown calculations use each prior-year close as baseline. `results/conclusions.md` MUST distinguish highest terminal wealth, risk-adjusted return, smallest drawdown, turnover/costs, and subperiod shifts; quantify concentration and expressly discuss survivorship, training-history/IPO bias, hindsight/vintage limits, realized path uncertainty, estimates, and missing execution costs/taxes. No fabricated winners or unearned significance claims.

### Required tests for these rules

Add offline synthetic tests for equal initial fees and correct total cash use; correct last-session signal/next-session execution calendar and first event per frequency; no same-close future use; 0.0001 **strict >** material turnover threshold; raw turnover/fees still include small orders; post-optimization stock-weight **strict < 0.0001** filter; positive-excess convex optimum and no-positive-excess fallback; one-business-day FRED availability lag; 2010/rolling-5-year asymmetry; mandatory concentration measures; correct subperiod boundaries; and missing/delisting handling. Config tests should assert these exact defaults.

---

### Precise mechanics and baseline limitations

- **Post-fee rebalance allocation:** Given pre-trade wealth `V`, pre-trade stock notionals `h_i` (include existing cash in `V`), target weights `w_i` and `c=0.001`, solve for post-fee wealth `X` using **`X = V - c * sum_i(abs(w_i*X - h_i))`**. Numerically solve by convergent fixed-point or bisection to absolute tolerance **USD 1e-8**; then execute shares toward `w_i*X`. Reject negative cash and reconcile final cash + shares values + fees to starting wealth; zero-trade decisions pay zero fee. Fractional shares permitted.
- **Net returns/CAGR** use **original $10,000** as starting wealth, **not** the approximately $9,990.01 remaining after initial fees. Initial fees count as a loss. Use time origin at the 2011-01-03 initial execution close and calendar-year day-count for CAGR. Include the initial fee in cumulative return but do not fabricate a previous-day market return for annualized volatility.
- **Exact rolling window:** for signal date `D`, include price observations on sessions satisfying `D - DateOffset(years=5) < date <= D`, e.g. 2011-01-31 uses price observations from 2011-01-31 back through 2006-02-01 (because 2006-01-31 is strictly excluded). Retrieve a preceding reference price if necessary for the first return. Initial estimation instead includes 2005-01-01..2010-12-31. Explain this deliberately asymmetric six-year vs five-year rule.
- **Free baseline missing/delisting policy:** Yahoo/yfinance data do not reliably cover delistings. Before portfolio formation **require positive, finite adjusted closes for every expected NYSE trading session across 2005–2025** (zero missing tolerated after per-ticker retrieval retries); exclude and log incomplete candidates *up front*. This knowingly uses 2025 survival and is a **major look-ahead selection/survivorship bias**: label every related result and graph **illustrative survivors-only**. If a selected stock later disappears or prices are missing, **stop/report**, do not silently sell, fill prices or set returns to zero. True point-in-time mode may only include delisted stocks with externally verified delisting payout/return mechanics. Document exclusion of post-2005 IPOs.
- **Annualization fixed:** annual arithmetic mean `mean(daily_simple_return)*252`, sample covariance `cov(daily_simple_returns)*252`, realized volatility `std(daily_simple_return, ddof=1)*sqrt(252)`. Report exact convention.
- **Historical source feasibility:** retrieving audited 2010 constituents and market caps is usually not feasible with simple public scripts; implement point-in-time tiers only if reliable sourced data exists, otherwise they must produce an actionable **source unavailable** error. Tier (3), the present-day 11-sector survivors-only convenience sample, is the expected executable public baseline; never mislabel it as historical 2010 top-cap selection.
- **Limits:** The 0.1% fee ignores spread, slippage and market impact and may understate actual costs; taxes on dividends and realized trades are not modeled. One 2011–2025 path is descriptive, not evidence of statistically significant dominance. No maximum holding cap may lead to extreme concentration; reporting holdings count, top weight and HHI is mandatory.
- **Benchmark:** optional only, omitted by default; an additional S&P 500 total-return proxy or same-universe equal-weight comparison must be labeled separately from the five strategies and only added after user approval.

## Implementation files and expected outputs

Write progressively: `README.md`, `PROJECT_PHASES.md`, `config.yaml`, `requirements.txt`, `.gitignore`, `src/{__init__,universe,download_data,preprocessing,optimization,backtest,metrics,plotting}.py`, `run_analysis.py`, `analysis.ipynb`, `tests/`. The repository itself is **Markowicz_rebalancing**; do not use a differently spelled hardcoded root directory in tree descriptions. On separately authorized execution, generate `results/{portfolio_metrics,portfolio_values,initial_weights,weight_history,trades,optimization_log,data_quality_report,subperiod_metrics}.csv`, four graphs `results/graphs/{portfolio_growth,risk_return,drawdowns,weight_evolution}.png` and data-grounded `results/conclusions.md`. Do **not** invent actual numeric conclusions before running.

**Stop after each saved phase and request permission for the next. No full execution, data download or test run without separate user approval.**
