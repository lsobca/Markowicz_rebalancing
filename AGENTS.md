# AGENTS.md — Markowitz portfolio optimization and rebalancing backtest

## Mission

Implement a reproducible, academically defensible **Python quantitative-finance research project** investigating:

> How does the frequency of repeatedly re-optimizing and rebalancing a US-equity portfolio with Markowitz mean–variance optimization affect its performance, risk, and trading costs over 2011–2025?

**Build the project, not merely a proposal. Download all necessary legitimate historical data yourself.** Do not ask the user to manually prepare stock-price CSVs. If important historical data cannot be sourced correctly, implement a documented fallback and explicitly disclose limitations; never fabricate or silently replace missing data.

**No dashboard, Streamlit, website, or GUI.** Produce a runnable Python workflow, Jupyter notebook for analysis, CSV outputs, static charts, and concise conclusions.

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

1. Find and **download a documented point-in-time candidate universe** of approximately 50–100 US-listed common stocks **known to be eligible by 2010-12-31**, diversified across sectors. A historically dated S&P 500 constituent snapshot is an acceptable source *if verifiable*, with a deterministic documented selection procedure that uses only then-available information. Do not use today's S&P 500 membership or future winners to build the 2010 universe.
2. Prefer data including stocks later delisted, acquired, bankrupt, or renamed, **with terminal outcomes**. Public free sources may be insufficient. Research and document source URL, snapshot date, provenance, selection method, licensing/availability, corporate actions, survivorship and delisting coverage. Treat currently available survivors-only data as a biased fallback, **not an unbiased conclusion**.
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
- Use scipy.optimize (e.g. SLSQP), numerical validation, multiple deterministic initializations and informative errors; the Sharpe objective is sensitive to estimated means/covariance. Handle degenerate covariance, non-finite returns, and optimizer failures *without silently using equal weights*.
- Filter `w < 1e-4` to zero, renormalize to total 1, and validate `weights >= 0`, sum approximately one, finite numbers. Store both raw and filtered weights. Log candidate names, selected stocks, predicted return/risk/Sharpe and concentration.
- Configurable risk-free rate: ideally source historically appropriate risk-free series without future observations, or explicitly default to 0% and label that assumption; for evaluating Sharpe, use the same declared convention and, if feasible, a time-aligned historical series. Do not introduce future knowledge.
- Default rolling window: **five calendar years** before each re-optimization; implement precise date boundaries/trading-day handling, rather than mistakenly training on all past data or always using 2005–2010.
- Initial optimization uses **2005-01-01 to 2010-12-31**. First implementation should keep these windows and all configuration centrally documented.
- Include a brief methodological warning: this research compares both frequency of **re-estimation** and trading, not merely rebalancing to fixed targets. It cannot isolate pure rebalancing cadence from the timing of weight-estimate updates.

## Time sequencing and trades: avoid look-ahead

- For each strategy, determine scheduled rebalance dates by the **actual trading calendar** (monthly/quarterly/semiannual/annual boundaries).
- At a decision date, use prices/returns **only through the previous completed trading session** if trades are executed at that day's close, or use the completed close then trade at the **next** available trading session. Choose one explicit, consistent timing convention; never estimate on the same close and pretend to trade at that close before it was known.
- Buy & Hold: allocate once and **never** trade again; weights drift with prices.
- Rebalanced strategies: recompute optimizer weights at scheduled times, apply the 1e-4 post-filter, trade toward target; transaction costs charged on both sells and buys. Preserve portfolio accounting/cash, ensuring costs cannot create negative cash. Include the cost of initial establishment equally for all five strategies (or explicitly choose zero initial trading cost consistently and explain), and distinguish it from subsequent rebalancing costs.
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
- Number of actual nonzero rebalance/trading events (different from scheduled dates).
- Turnover with a clearly specified formula (e.g. gross traded notional / pre-trade portfolio value summed over events); separate sells/buys if helpful.
- Sum of transaction fees in USD; optional percentage of initial capital.
- Optionally expose concentration, number of holdings, and largest weight to explain outcomes.

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
3. Implement, install dependencies, run tests, then run the historical experiment **if genuine data access allows**.
4. Save all actual outputs and charts, with labelled methodology and a conclusion that answers the question. If historical data are insufficient, produce runnable code/tests and a clear blocker report rather than made-up quantitative conclusions.
5. Update README with run commands, assumptions, input provenance, date windows, filter interpretation, warnings (survivorship, delisting, estimates, transaction-cost simplifications), and file descriptions.
6. Explicitly report what has been completed, any warnings, which downloaded data were used, and which steps could not be executed.

**Do not change user-approved parameters without saying so. Do not add unrelated features or a dashboard.**
