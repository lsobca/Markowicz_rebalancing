# AGENTS.md — Markowitz portfolio optimization and rebalancing backtest

## Mandatory phased workflow for Codex — user approval after EVERY phase

**This section takes precedence over any instructions elsewhere in this file about implementing, downloading, installing, testing, executing or completing the entire project in one go.** The user wants incremental coding and saving, **not automatic validation**.

### Working protocol

1. **Start with Phase 1 ONLY.** Do not create code/files belonging to later phases, even if they are trivial.
2. For each authorized phase: read the existing repository, add/edit **only that phase's files**, save/commit the completed changes to GitHub on the working branch, and stop.
3. **Do not run code, scripts, unit tests, notebooks, linters, formatters, dependency installation, data downloaders or full backtests. Do not independently verify correctness.** Write coherent code and tests (in their allocated phase), but **do not execute them**. Git operations needed solely to inspect and save files are fine. Do not claim any unexecuted code works.
4. After saving the phase, respond briefly **in Slovak** with (a) phase number and completed files, (b) commit reference/link if available, (c) what comes next and (d) the explicit question **"Mám pokračovať ďalšou etapou?"**. **STOP and await an affirmative user response.** Never advance to the next phase without confirmation. A request to modify the current phase is not permission to start another one.
5. If a phase cannot be completed due to missing data, access or permissions, commit whatever useful source/documentation can be saved, disclose the blocker, and ask whether to continue or adjust that phase. No fabricated data or figures.
6. Full-download and computation requirements below describe the **end goal and functionality to implement**, not permission to run the workflow. Data must eventually be downloadable automatically by a single scripted command, but while following this phased workflow **write the download code without executing it**. Only a subsequent explicit user request can authorize downloads/runs.
7. Keep the approved quantitative-finance methodology in this document unchanged unless the user specifically authorizes a modification. Do not create a dashboard.

### Phase 1 — Skeleton and configuration ONLY

Create/update `README.md` (scope, 5 strategies, roadmap, all agreed assumptions, disclaimer that nothing has been run), `config.yaml` (all binding numeric defaults, date window, fee/timing/risk-free settings), `requirements.txt`, `.gitignore`, empty Python package `src/__init__.py` and necessary empty directory placeholders. A concise `PROJECT_PHASES.md` is allowed. **No download, optimizer, backtest, plots, or tests yet.** Commit and ask for approval.

### Phase 2 — Historical universe and download infrastructure

Implement `src/universe.py` and `src/download_data.py` plus data provenance specification/manifests or templates as needed. Code should download stock universe, stock prices and FRED DGS3MO **when run later**, implement the documented 2010 historical-vs-survivors-only selection tiers, availability/IPO/delisting flags, caching and retries. No downloads or real API calls now; no actual results or invented source records. Commit and ask.

### Phase 3 — Cleaning and returns

Implement `src/preprocessing.py`: adjusted price loading/validation, missing-value policy, adjusted total-return proxy interpretation, synchronized dates, daily returns, quality flags and clean saved-data outputs to be generated upon future execution. No data execution. Commit and ask.

### Phase 4 — Markowitz optimizer

Implement `src/optimization.py` with positive-excess convex formulation, the deterministic all-nonpositive-excess contingency, risk-free handling, five-year rolling/initial six-year windows, strict post-optimization `0.0001` stock-weight filter, normalization and mandatory concentration diagnostics. **Do not yet build the backtest.** Commit and ask.

### Phase 5 — Five-strategy backtest engine

Implement `src/backtest.py`: Buy & Hold and monthly/quarterly/semiannual/annual strategies; exact period-end signal and next-session-close execution timing; first 2011 rebalance dates; fixed fee including initial trades; shares/cash accounting; no look-ahead; trades, drift, gross turnover and material-event threshold; outputs generated upon future run. Commit and ask.

### Phase 6 — Metrics and static charts

Implement `src/metrics.py` and `src/plotting.py`: requested return/risk/fees/turnover/concentration summary metrics, period-specific 2011–15/2016–20/2021–25 metrics, four static chart functions and export formatting. No run, no invented completed chart or result CSV. Commit and ask.

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

**This section is mandatory, overrides any older generic alternatives below, and must be reflected in `config.yaml`, README, code and tests.** Do not offer multiple equally default conventions.

### Timeline and accounting (fixed)

- Set `initial_capital_usd: 10000`, `fee_rate: 0.001`, `initial_purchase_fee: true`, `initial_fee_policy: charge_all_portfolios`, `signal_convention: period_last_session_close`, `execution_convention: next_session_close`, `material_rebalance_turnover_threshold: 0.0001`, `weight_filter_threshold: 0.0001` in config.
- **Charge the 0.1% trading fee on gross executed notional for every buy and sell, including the initial allocation for all five portfolios and Buy & Hold.** Purchase notional is funded from $10,000 less its fee (invest 10000/1.001, not 10000 and then borrow the fee). Keep cash nonnegative; every strategy receives identical starting conditions. Count/reconcile fees and gross turnover; distinguish initial purchases from subsequent rebalancing.
- **Signal at the close of the last actual trading session of the relevant calendar period; estimate exclusively from data through that completed close; execute at the close of the NEXT trading session**, so the freshly estimated allocation affects only subsequent returns. Initial training ends with the last 2010 session (2010-12-30), and initial allocation executes at the first 2011 session close (2011-01-03). All portfolios share this execution/valuation basis. No trades after the final 2025 session. The late-December-2025 annual signal therefore has no within-sample execution.
- Signals: monthly = last trading session of every month; quarterly = last trading session of March/June/September/December; semiannual = last trading session of June/December; annual = last trading session of December. First 2011 signals and trades: monthly Jan 31 -> Feb 1, quarterly Mar 31 -> Apr 1, semiannual Jun 30 -> Jul 1, annual Dec 30 -> Jan 3 2012 (subject to verified actual NYSE calendar). **No immediate re-optimization after initial purchase in January 2011.**
- **Material rebalance event for reporting**: a *post-initial* executed rebalance date with `gross_notional / pre_trade_wealth > 0.0001` (strictly greater than 0.01% of pre-trade value). This is NOT a minimum order size: include all positive executions in fees, gross turnover and bookkeeping, even if smaller. Report scheduled events, events with any positive trading, and material rebalance count separately. Keep this distinct from the 0.0001 *stock-weight* filter.
- **Turnover**: sum over execution dates of `sum(abs(executed buy/sell notionals))/portfolio_value_before_orders`; label this **gross two-sided turnover**. Report post-initial turnover separately from initial purchases, to avoid penalizing all portfolios equally in comparisons.

### Universe / source (fixed, with clearly labeled feasibility fallback)

- The desired **unbiased historical experiment** needs contemporaneous security identities, a 2010-12-31 constituent roster and market caps, adjusted total returns, and reliable returns/cash proceeds for delistings. **yfinance cannot be relied on to provide a complete delisted equity universe; its ordinary free-data run is expected to be survivors-only and biased**, not a rare edge case. Document possibility of CRSP through WRDS/university access (including VŠB), Norgate, and assessed vendors. Tiingo prices alone do not prove point-in-time universe or delisting coverage. Do not fabricate either.
- **Primary historical universe construction rule**: source *documented 2010-12-31 S&P 500 membership, GICS sector as of 2010 and 2010-12-31 market capitalization*. Within each of the **10 sectors at that date** select **top 10 eligible common-stock issuers by 2010-12-31 market capitalization per sector**, target 100, remove duplicate issuers/share classes; ties deterministically by contemporaneous permanent identifier. Retrieve cap from a verified dated archive/vendor or compute only from trustworthy 2010 price and historical shares outstanding, consistently adjusted for share splits. **Never substitute today's market cap, membership or sector assignments as 2010 data.** Exclude and log assets with no complete 2005–2010 estimation history. This deliberately excludes post-2005 IPOs: report IPO/history eligibility bias. Keep the original universe fixed thereafter except for properly modeled corporate events.
- **Executable free-data baseline**, expected when dated reliable constituents/caps/delistings are not available: (1) try the historical top-10-per-sector rule; (2) if dated 2010 membership and sectors exist but historic caps do not, take the first 10 by stable historical identifier alphabetically per 2010 sector, then use accessible prices, recording every missing/delisted company; (3) if no documented 2010 snapshot exists, use a sourced current S&P 500 list, first 10 tickers alphabetically per currently recorded sector with usable 2005–2010 price history, no future-performance selection, then document all excluded tickers. **Label tiers (2) and (3) prominently "illustrative survivors-only", and tier (3) "strongly biased current-constituent convenience sample".** Persist the unfiltered candidate roster, selection and exclusions; never imply that these samples are historical top-cap 2010 universes. Auto-download and cache reproducibly; do not require hand-prepared CSVs.
- Use vendor `Adj Close` (or auto-adjusted close with documented semantics) as a **backward adjusted total-return proxy**, incorporating splits and assuming reinvestment of dividends, never counting dividends a second time. The adjustment reflects the **data vendor's retrieval-date vintage**, not a contemporaneously saved 2010 feed; save as-downloaded data, download timestamp, source and checksum; warn of vintage changes and possible imperfect treatment of special dividends, mergers and delistings. Never replace missing/delisted observations by zeros or unlimited forward-fill.

### Risk-free inputs and optimization (fixed)

- Default `rf_mode: fred_dgs3mo`: auto-download **FRED DGS3MO**, the annualized yield on a 3-month constant-maturity US Treasury (risk-free proxy, **not** investable realized Treasury-bill returns). At optimizer signals use the last **previously available published** value; to avoid release-time leakage, use at least one full business-day publication lag absent precise release timestamps. Convert percent to decimal and use annual-rate units against annualized mean/covariance. For ex-post Sharpe use aligned daily excess returns and a documented daily-rate transformation (e.g. `(1+annual_rate)**(1/252)-1`), no interpolation from future observations. If FRED download fails and no validated cached copy exists, fail explicitly for primary runs; allow `--rf-mode zero-sensitivity` ONLY as prominently labeled 0% sensitivity, never as a silent default. Report FRED provenance and availability.
- Default optimizer when at least one stock has `mu_i > rf`: **positive-excess max-Sharpe convex transformation** `min_x x' Sigma x`, subject to `(mu-rf)'x = 1`, `x >= 0`, then `w=x/sum(x)`. Use cvxpy with recorded solver/regularization; verify finite solution, constraints and objective and then apply the fixed post-optimization weight filter `w < 0.0001` -> zero, normalize. No shorting, no extra weight cap. Handle singular covariance explicitly (regularize only transparently); do not silently substitute equal weights.
- **If no expected stock return exceeds rf** (no positive excess expected return), the convex positive-excess constraint is infeasible. Use deterministic disclosed emergency contingency: **100% in the stock with largest `mu_i-rf`** (tie: lexicographically smallest stable ID), record `optimizer_status=nonpositive_excess_fallback` and warn this is **not mathematically the guaranteed max-Sharpe solution for all-negative excess-return cases**; no arbitrary equal-weight fallback. If chosen asset volatility is zero/invalid, halt with an explicit error. If other solver failures occur, halt/report instead of fabricating a portfolio.
- Initial training window **2005–2010 inclusive = six calendar years**; every later window = trailing **five calendar years**, intentionally asymmetric per user request. Explain its effect on comparability in README and conclusions.
- **Mandatory concentration reporting**: holdings count, largest holding share, HHI = sum(weight^2) at initial and all later signal dates, with summary statistics across time. Discuss unstable mean estimates, noise and potential concentration caused by no cap, especially monthly re-optimization.

### Interpretation and statistical caution (fixed)

- 0.1% modeled fee excludes bid/ask spread, slippage, market impact, financing, and taxes on dividends/realized gains. Explicitly state the cost estimate may be understated, and **no taxes are modeled**.
- Alongside 2011–2025 overall metrics, **report the fixed subperiods 2011–2015, 2016–2020 and 2021–2025**, with clearly defined start-of-subperiod valuation and risk calculations. A single observed market path does **not** establish statistical significance; do not claim statistically reliable superiority without an appropriate inference procedure.
- **Optional benchmark, not part of the five-portfolio competition:** add a separately labeled S&P 500 total-return proxy (e.g. SPY adjusted close with assumptions) **only if downloads are reliable and it's clearly separated from individual-stock candidate universe**. Also an equal-weight 1/N strategy is optional, with the same universe, fees and timing. Benchmarks do not substitute for any of the five user-requested portfolios. If benchmarks are omitted, explain that comparative claims concern the five strategies, not whether Markowitz beats the broad market.
- `results/conclusions.md` MUST distinguish highest terminal wealth, risk-adjusted return, smallest drawdown, turnover/costs, and subperiod shifts; quantify concentration and expressly discuss survivorship, training-history/IPO bias, hindsight/vintage limits, realized path uncertainty, estimates, and missing execution costs/taxes. No fabricated winners or unearned significance claims.

### Required tests for these rules

Add offline synthetic tests for equal initial fees and correct total cash use; correct last-session signal/next-session execution calendar and first event per frequency; no same-close future use; 0.0001 **strict >** material turnover threshold; raw turnover/fees still include small orders; post-optimization stock-weight **strict < 0.0001** filter; positive-excess convex optimum and no-positive-excess fallback; one-business-day FRED availability lag; 2010/rolling-5-year asymmetry; mandatory concentration measures; correct subperiod boundaries; and missing/delisting handling. Config tests should assert these exact defaults.

---

## Confirmed user requirements (do not silently change)

- Asset class: **individual publicly traded US stocks**, **not ETFs**.
- Initial estimation period: **2005-01-01 through 2010-12-31**.
- Out-of-sample investment and evaluation: **2011-01-01 through 2025-12-31** (trade on actual trading sessions; initial allocation on first eligible session of 2011).
- **Five independent portfolios**, each initially worth **USD 10,000**, beginning with identical holdings and weights:
  1. Buy & Hold — no subsequent trades or re-optimization.
  2. Monthly — re-estimate Markowitz weights and rebalance monthly.
  3. Quarterly — re-estimate and rebalance quarterly.
  4. Semiannual — re-estimate and rebalance every six months.
  5. Annual — re-estimate and rebalance yearly.
- All four actively rebalanced strategies use a **trailing five-year rolling estimation window**, ending at the last date whose data were actually available at the decision time. The *initial* window is 2005–2010, as explicitly requested, even though it spans six calendar years.
- Markowitz optimization objective: **maximize the ex-ante Sharpe ratio**; estimate expected returns and covariance using historical adjusted total-return series; configure and document risk-free-rate assumption.
- Long-only: weights >= 0; fully invested: weights sum to 1; **no user-imposed maximum weight per stock**.
- **Fixed numeric post-optimization threshold = 0.0001 of portfolio weight (0.01%)**, NOT 0.01 and NOT USD 1. After optimizing, set weights *strictly below 0.0001* to zero, then renormalize surviving weights to 1. Equal-to-threshold weights survive. This is a **post-optimization filter**, not a positive lower bound on every candidate and not a dollar threshold. Apply at initial allocation and at each re-optimization. Report if the heuristic changes the objective or portfolio concentration; do not invent a maximum-weight rule.
- Default trading fee assumption: **0.1% of gross traded notional** (sum of absolute buy and sell notionals), configurable. Include fees consistently; model zero fees as a useful comparison.
- Prefer portfolio units allowing fractional shares, so fractional holdings/very small positions can be simulated.
- Metrics: final value, total return, CAGR, annualized volatility, Sharpe ratio, maximum drawdown, number of actual nonzero rebalances, turnover, and total transaction costs.
- Charts: growth of all five portfolio values; risk vs return scatter; drawdown time series; evolution of stock weights for representative strategies. Save static PNGs. No interactive dashboard.

## Critical integrity and data requirements

### Historical universe and survivorship bias
Markowitz **assigns weights within a candidate universe**, it does not create a historically valid investable universe from thin air.

1. Apply the exact historical 2010 sector-top-10-by-2010-market-cap rule, and its explicit reproducible, honestly labeled data-access fallbacks described in the binding specification.
2. Prefer data including stocks later delisted, acquired, bankrupt, or renamed, **with terminal outcomes**. Public free sources may be insufficient. Research and document source URL, snapshot date, provenance, selection method, licensing/availability, corporate actions, survivorship and delisting coverage. Expect a survivors-only **baseline** under free yfinance access, prominently label it biased, and do not report it as an unbiased historical conclusion.
3. Keep the candidate universe fixed for this experiment to isolate the impact of optimization/rebalancing frequency. Membership in a *portfolio* can vary because optimized weights cross the threshold.
4. Never silently delete candidates that disappear during 2011–2025 or replace disappearing stocks with surviving winners. Handle delisting/mergers with documented total-return/cash proceeds or delisting return rules from reliable data. If not available, flag and report, and do not claim to have an unbiased backtest. Clearly separate data limitations from numerical results.
5. Validate complete usable training histories for the selected stocks and flag exclusions with reasons. Avoid hindsight-based exclusion based on 2011–2025 outcomes. If a fully correct data set cannot be acquired, provide a transparent, executable **illustrative survivors-only analysis** (separately labeled), plus a clear note that it cannot support strong historical claims.
6. Provide the exact stock universe in a CSV including ticker, issuer/name if available, historical identifier(s) if available, selection date/source, and exclusions; keep a data-provenance manifest. Account for ticker changes and company identities rather than assuming tickers are permanent.

### Fetching and cleaning prices
- Implement a script or CLI such as `python -m src.download_data` / `python run_analysis.py` that **automatically obtains the needed data** (including the candidate list where legitimately obtainable), saves reproducible local caches under `data/`, and then runs preprocessing and analysis; no manual CSV preparation.
- Use `yfinance` or another suitable lawful API for stock prices where practical; adjusted prices must appropriately incorporate dividends and splits; explicitly document whether adjusted-close series are total-return approximations and how cash distributions are handled. Data should include the full estimation and testing horizons, with enough warm-up records.
- Do not hardcode unverified ticker lists as if they were a historical point-in-time snapshot. If providing an illustrative static list, label it explicitly as an illustrative fallback and document its limitations.
- Handle API errors, batching, rate limits, retries with backoff, caching, reproducibility, invalid/non-trading days, missing observations, ticker transitions, delisting and corporate actions. Fail loudly if meaningful data are missing; **never treat missing prices as zero returns or blindly forward-fill through a delisting**.
- Export cleaned prices/returns and a data-quality report. Log exact source timestamps, retrieved dates, tickers included/excluded, reasons, and available windows.
- If network access is unavailable in a developer/CI environment, unit tests must still run offline on synthetic data; a full historical run must give a clear actionable error or use previously cached real data, never substitute synthetic data for actual market results without labeling it.

## Optimization methodology

- Set daily simple total returns `r[t] = P[t]/P[t-1] - 1`, where `P` is an appropriately adjusted total-return-compatible price.
- Annualize expected simple returns consistently (e.g. daily arithmetic mean × 252) and covariance (daily covariance × 252). Explicitly document the chosen convention and caveats.
- Maximize `Sharpe(w) = (w·mu - rf_annual) / sqrt(w.T @ Sigma @ w)`.
- Constraints: `sum(w)=1`, `w >= 0`, **no upper bound except the mathematically implicit <= 1**. Do not add a 20% cap.
- Use the convex positive-excess Sharpe transformation in the binding specification, plus explicit nonpositive-excess contingency, numerical checks and clear errors. The Sharpe objective is sensitive to estimated means/covariance.
- Filter `w < 1e-4` to zero, renormalize to total 1, and validate `weights >= 0`, sum approximately one, finite numbers. Store both raw and filtered weights. Log candidate names, selected stocks, predicted return/risk/Sharpe and concentration.
- Configurable risk-free rate: download FRED DGS3MO with publication lag as specified above; for evaluating Sharpe, use the same declared convention and, if feasible, a time-aligned historical series. Do not introduce future knowledge.
- Default rolling window: **five calendar years** before each re-optimization; implement precise date boundaries/trading-day handling, rather than mistakenly training on all past data or always using 2005–2010.
- Initial optimization uses **2005-01-01 to 2010-12-31**. First implementation should keep these windows and all configuration centrally documented.
- Include a brief methodological warning: this research compares both frequency of **re-estimation** and trading, not merely rebalancing to fixed targets. It cannot isolate pure rebalancing cadence from the timing of weight-estimate updates.

## Time sequencing and trades: avoid look-ahead

- For each strategy, determine scheduled rebalance dates by the **actual trading calendar** (monthly/quarterly/semiannual/annual boundaries).
- At a decision date use completed signal-session close to estimate and execute only at the following trading-session close, as fixed above; never estimate and trade at the same close.
- Buy & Hold: allocate once and **never** trade again; weights drift with prices.
- Rebalanced strategies: recompute optimizer weights at scheduled times, apply the 1e-4 post-filter, trade toward target; transaction costs charged on both sells and buys. Preserve portfolio accounting/cash, ensuring costs cannot create negative cash. Include the mandatory 0.1% fee on initial purchases for all five strategies, and distinguish it from subsequent rebalancing costs.
- Track shares, cash, fees, executed trade notional, turnover, number of nonzero trade events, current weights, target weights, daily portfolio value, daily net returns and drawdowns.
- Model exact treatment of end-of-period decisions: do not execute trades after 2025-12-31; consistently define final close and starting price observation. Avoid inconsistent performance-start bases.
- If a stock goes missing or is delisted, apply documented valid handling or stop/report for that run instead of allowing values to disappear.
- Keep all five strategies comparable in dates, prices, initial assets, and trading-fee assumptions.

## Evaluation and visualizations

Calculate and clearly define:
- Final portfolio USD value and total return (net of trading fees).
- CAGR from actual elapsed years, based on net initial/final wealth.
- Annualized daily-return volatility (sqrt(252)).
- Ex-post annualized Sharpe ratio with documented risk-free assumption.
- Maximum drawdown based on running historical highs.
- Number of material rebalance/trading events under the strict gross-notional threshold defined above (different from scheduled dates).
- Turnover with a clearly specified formula (e.g. gross traded notional / pre-trade portfolio value summed over events); separate sells/buys if helpful.
- Sum of transaction fees in USD; optional percentage of initial capital.
- Mandatory concentration metrics: holding count, largest weight and HHI, at optimization dates and summarized across time.

Export:
- `results/portfolio_metrics.csv`
- `results/portfolio_values.csv` (daily five-strategy series)
- `results/initial_weights.csv`
- `results/weight_history.csv`
- `results/trades.csv`
- `results/optimization_log.csv`
- `results/data_quality_report.csv`
- `results/graphs/portfolio_growth.png`
- `results/graphs/risk_return.png`
- `results/graphs/drawdowns.png`
- `results/graphs/weight_evolution.png`
- `results/conclusions.md`: address the research question using actual computed values, distinguishing highest final wealth, best risk-adjusted performance, lowest drawdown, turnover/costs, and data caveats. **Never claim a winner without completed actual-data results.**

For weight graphs, because the universe may have many stocks, plot the most influential names with an 'Other' category, with clear labels and a legend; make charts readable and save them as PNG using matplotlib. A notebook may display the saved charts.

## Implementation / deliverables

Create a maintainable repository, for example:

```text
Markowicz_rebalancing/
  AGENTS.md
  README.md
  requirements.txt
  .gitignore
  config.yaml
  run_analysis.py
  analysis.ipynb
  src/
    __init__.py
    universe.py
    download_data.py
    preprocessing.py
    optimization.py
    backtest.py
    metrics.py
    plotting.py
  tests/
    test_optimization.py
    test_rebalancing.py
    test_lookahead.py
    test_accounting.py
    test_metrics.py
  data/
    .gitkeep
  results/
    graphs/
      .gitkeep
```

Exact file names may vary if the resulting project is simpler and clearer; **do not create a dashboard**. Prefer pure tested Python functions for calculations and a notebook for narrative, charts and tables. Pin or constrain dependencies in `requirements.txt`. Provide clear instructions for Python environment setup and **one command** that downloads real data and runs the end-to-end research. Use cache-by-default plus an explicit `--refresh-data` option where feasible. Include configuration for fee rate, initial capital, estimation and test dates, minimum weight threshold, risk-free convention, universe source and rolling lookback. Be deterministic where possible.

Tests must operate offline on small synthetic assets with expected results, including:
1. weights nonnegative, sum to one, and post-filter threshold is exactly **0.0001**;
2. a weight of exactly 0.0001 is retained; a weight below it is discarded;
3. Buy & Hold truly makes no trades after initial purchase;
4. rebalancing occurs only at correct monthly/quarterly/semiannual/annual schedules;
5. an extreme future return has no effect on an earlier optimizer decision;
6. consistent cash/shares accounting and round-trip gross turnover and fees;
7. portfolio wealth/metrics match analytically calculable synthetic examples;
8. missing prices/delistings are never silently treated as zero return;
9. reproducibility of optimized weights from an identical dataset;
10. no-trade dates do not generate artificial transaction costs.

## Success criteria / task completion

1. Inspect the repository first; preserve any existing user code.
2. Research and acquire the strongest legitimately accessible **historical point-in-time universe and data**, document limitations and sources rather than inventing them.
3. Implement and commit **only the user-approved phase**. Do **not** install dependencies, execute downloads, run tests, run notebooks or launch the historical experiment unless the user later explicitly requests that separate execution stage.
4. Implement code that will save actual outputs and charts **when separately authorized to run**, with a conclusion generator that answers the question only from computed data. During the phased coding-only workflow save templates/source, not fabricated outputs; document blockers.
5. Update README with run commands, assumptions, input provenance, date windows, filter interpretation, warnings (survivorship, delisting, estimates, transaction-cost simplifications), and file descriptions.
6. After **each phase**, state the files and commit saved, unexecuted status, known limitations, and ask for permission to continue to the next phase. Never infer authorization.

**Do not change user-approved parameters without saying so. Do not add unrelated features or a dashboard.**
