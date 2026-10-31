# Market Signal Lab

A reproducible local research project that turns daily ETF market data into trading signals, evaluates them chronologically, and executes them through a compiled **C++17 simulator**. Python handles data preparation, model fitting, diagnostics, and reporting; SQLite stores auditable paper-trading events.

The objective is trustworthy research evidence, including negative results. This is an independent research project. It does not place live broker orders or establish profitable alpha.

## What the project does

- Downloads Yahoo Finance history or imports documented per-symbol OHLCV CSVs.
- Validates prices, duplicates, exchange sessions, coverage, and corporate-action discontinuities; caches normalized data in Parquet.
- Compares a fixed momentum rule, Ridge regression, and histogram gradient boosting against cash and equal-weight buy-and-hold.
- Uses expanding walk-forward evaluation, chronological inner validation, and label-availability purging.
- Exports versioned signals to a real C++ cash-and-position accounting engine.
- Models next-open execution, integer share sizing, commissions, slippage, missing prices, and rejected orders.
- Produces performance, cost stress, signal decay, feature diagnostics, uncertainty estimates, and reconciled attribution.
- Supports restart-safe historical paper replay and manual daily signal generation/settlement.

## Latest historical results

Yahoo Finance data was downloaded on **28 October 2026** for **SPY, QQQ, IWM, EFA, EEM, TLT, GLD, and XLE**. The snapshot contains **34,208 symbol-session observations**: 4,276 per ETF, covering every expected XNYS session from 2 January 2009 through 31 December 2025.

The following results come from the saved C++ simulation over **3 January 2013–31 December 2025**, starting with $100,000. Base costs are **1 bp commission plus 5 bps adverse slippage per side**, charged on traded reference notional. Cash earns no interest; ending holdings are marked rather than liquidated.

| Strategy | Gross cumulative return | Net cumulative return | Net annualized return | Maximum drawdown |
|---|---:|---:|---:|---:|
| Momentum | 172.24% | 75.37% | 4.43% | −15.86% |
| Ridge | 250.00% | 51.71% | 3.27% | −40.78% |
| Gradient boosting | 341.05% | 32.28% | 2.18% | −30.67% |
| Equal-weight buy-and-hold | 261.40% | 261.34% | 10.41% | −27.68% |
| Cash | 0.00% | 0.00% | 0.00% | 0.00% |

All three active strategies trailed buy-and-hold after costs. Exposures and risks differ, so this is not a risk-matched alpha comparison. The data is a current-vintage adjusted snapshot, not a point-in-time archive or live trading record.

Saved results from the completed run are in [`results/yahoo-20261028/`](results/yahoo-20261028/):

- Research report: [`report.md`](results/yahoo-20261028/report.md)
- Full performance table: [`summary.csv`](results/yahoo-20261028/summary.csv) and fold/year/holdout results: [`periods.csv`](results/yahoo-20261028/periods.csv)

Other generated data and artifacts are ignored by Git; a fresh checkout must generate its own runs in `artifacts/`.

## Requirements

- Python **3.12** is the tested environment.
- A C++17 compiler: Apple Clang on macOS, or a suitable GCC/Clang toolchain on Linux.
- GNU Make and a POSIX shell. Windows users should use WSL; native Windows commands are not provided.
- Internet access for initial dependency installation and Yahoo downloads. Cached research and the synthetic demo run offline after setup.

Pinned packages are listed in [requirements.txt](requirements.txt), including NumPy, pandas, scikit-learn, Matplotlib, PyArrow, exchange-calendars, pytest, CMake, and yfinance. `make setup` creates a project-local `.venv` and installs them. No paid data service, API key, broker account, or cloud service is required for the Yahoo workflow.

## Quick start: offline demo

Run commands from the repository root:

```sh
make setup
make build
make test
make demo RUN=offline-example
```

Open `artifacts/offline-example/report.md` after completion. This demo generates deterministic **synthetic** data on real exchange-session dates; its results are engineering fixtures, not market measurements.

Use a new `RUN` name for another experiment. The pipeline refuses to overwrite an existing run directory.

## Download and evaluate real data

Download a new snapshot, then run the same frozen experiment:

```sh
.venv/bin/python -m research.download_yahoo \
  --output data/raw/yahoo-new

OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/market-signal-mpl \
.venv/bin/python -m research.run \
  --raw data/raw/yahoo-new/normalized \
  --provider yahoo-yfinance \
  --documentation docs/yahoo-data.md \
  --run-id yahoo-new \
  --config configs/base.yaml
```

The downloader's date range is fixed to 2009-01-01 inclusive through 2026-01-01 exclusive. It preserves provider-returned tables in `provider/`, creates consistently adjusted imports in `normalized/`, and saves retrieval times, coverage, action counts, and checksums in `download_manifest.json`.

Existing provider files are reused without redownloading. Choose a **new output directory** to obtain a fresh snapshot. A new output name does not extend the requested date range. See [Yahoo data methodology](docs/yahoo-data.md) for normalization and current-vintage limitations; the provenance document records the original snapshot, while each download manifest records its own retrieval metadata.

To repeat the already-downloaded snapshot without network access:

```sh
OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/market-signal-mpl \
.venv/bin/python -m research.run \
  --raw data/raw/yahoo-20261028/normalized \
  --provider yahoo-yfinance \
  --documentation docs/yahoo-data.md \
  --run-id yahoo-replay \
  --config configs/base.yaml
```

### Import another provider

Supply one CSV per symbol, named for the symbol or containing a `symbol` column. Required fields are:

```text
session,open,high,low,close,volume
```

`date` is accepted as an alias for `session`; column names are normalized to lowercase. Provide consistently adjusted OHLC prices, not adjusted close mixed with incompatible opens. Create a provider document describing source URLs, download time, adjustment conventions, coverage, and known limitations.

```sh
.venv/bin/python -m research.store \
  --raw data/raw/provider \
  --dest data/processed/provider \
  --provider PROVIDER \
  --documentation docs/my-provider.md
```

Then use `research.run` with that raw directory and provenance document, following the Yahoo example. The historical pipeline requires the fixed eight-symbol universe. Inspect data-quality findings before interpreting any results.

## Research protocol

The [frozen protocol](docs/protocol.md) defines the experiment before evaluation. The default [configuration](configs/base.yaml) records dates, universe, seed, capital, and costs.

| Stage | Period or rule |
|---|---|
| Feature warm-up | 2009 only |
| Initial training | Begins in 2010, approximately three years |
| Development OOS evaluation | 2013–2023 |
| Retrospective final evaluation | 2024–2025 |
| Outer refits | Expanding history, six-month test windows |
| Inner validation | Last six months of available training history |
| Label purge | Training label must mature before the fit cutoff |
| Momentum | Trailing 20-session return divided by 20 |
| Ridge candidates | Alpha 1 or 100 |
| Boosting candidates | 15 or 31 leaves; 50 iterations; learning rate 0.05 |
| Shared portfolio policy | Rank positive forecasts; top four receive 24% targets each; remainder stays in cash |

Features are trailing 1/5/20/60-session returns, distance from a trailing mean, realized volatility, daily range, and trailing adjusted dollar volume. Preprocessing is fitted on training rows only. Symbols share chronological fold boundaries, and accounts remain continuous across refits.

Some settings are intentionally implemented in the research modules rather than exposed as configuration switches. The pipeline enforces the frozen start/end/final-period dates and seed; changing the study requires an explicit protocol and harness update. The final period is retrospective, not a substitute for a future live track record.

### Signal and execution timing

| Event | Earliest time |
|---|---|
| Observe session `t` OHLCV | After session `t` closes |
| Issue signal | Close `t` + one minute |
| Execute | Open `t+1` |
| Label becomes known | Open `t+2` |

The primary prediction target is:

```text
open[t+2] / open[t+1] - 1
```

The simulator marks equity at the close, so portfolio daily returns and predictive open-to-open labels are different measurements. Contracts use UTC timestamps; sessions follow the XNYS calendar, including early closes.

## Simulator and execution assumptions

The production engine is `build/market_sim`, compiled from [simulator/main.cpp](simulator/main.cpp). Python exports desired weights; C++ sizes integer normalized shares using pretrade open equity, processes sells before buys, and limits purchases to available cash.

Fees and slippage are explicit cash costs counted once. The engine records fills, positions, cash, equity, stale marks, rejection states, and per-symbol attribution. Daily equity changes reconcile to overnight movement plus post-trade intraday movement minus fees and slippage.

The target-weight contract caps individual weights at 25%; active strategies use 24%. Price drift between rebalances and the buy-and-hold benchmark can exceed that target limit. Missing prices never produce fabricated fills; held positions may retain flagged stale marks.

The report compares zero, half, base, and double transaction costs, plus an additional execution-session delay. Gross results are a separate zero-cost account, so cash and rounding may differ from the net account. TWAP/VWAP scheduling is demonstrated on **synthetic intraday fixtures only**; daily OHLCV does not establish intraday execution advantages.

See [CSV contracts and accounting rules](docs/contracts.md).

## Reports and saved artifacts

Each run writes `artifacts/<run-id>/`:

| Artifact | Contents |
|---|---|
| `report.md`, `performance.png`, `diagnostics.png` | Narrative report and plots |
| `summary.csv`, `periods.csv` | Overall, development, final, yearly, and fold performance |
| `predictive_quality.csv` | MSE versus a zero-return predictor and rank IC |
| `stress.csv`, `decay.csv`, `uncertainty.csv` | Cost/delay scenarios, executable signal horizons, block-bootstrap estimates |
| `diagnostics.csv`, `ridge_coefficients.csv` | Development ablations, learning-history/permutation diagnostics, coefficients |
| `predictions.parquet`, `folds.csv`, `experiments.csv` | OOS predictions, temporal boundaries, hyperparameter attempts |
| `*-signals.csv`, `market.csv` | Versioned C++ inputs |
| `*-equity.csv`, `*-fills.csv`, `*-positions.csv`, `*-attribution.csv` | C++ accounting outputs |
| `manifest.json`, `ledger_manifest.json` | Run hashes/versions/runtime and immutable replay provenance |
| `store/` | Validated Parquet market data and import metadata |
| `paper.sqlite`, `replay_check.json` | Historical replay events and restart checks |
| `*.pkl` | Fitted local model pipelines |

Regenerate a report from saved artifacts:

```sh
make report RUN=yahoo-20261028
```

Reports are regenerated from saved outputs; this command does not retrain models or rerun execution. Model pickle files should only be loaded from trusted sources.

## Paper trading

### Replay a completed research run

```sh
.venv/bin/python -m paper.loop \
  --run artifacts/yahoo-20261028 \
  --asof 2026-01-01T00:00:00Z
```

The historical run's replay was interrupted after 11 events, resumed, and repeated. It retained **41,147 unique events**, including on a subsequent CLI rerun. SQLite transactions and deterministic event IDs prevent duplicates. This is historical simulation; no live orders are submitted.

### Generate daily signals and settle later

The manual daily commands require fresh, consistently adjusted provider CSVs through the latest completed session, along with their provenance document:

```sh
.venv/bin/python -m paper.daily \
  --raw data/raw/provider \
  --provider PROVIDER \
  --documentation docs/my-provider.md

# After later sessions close, refresh the provider import and settle:
.venv/bin/python -m paper.settle \
  --raw data/raw/provider \
  --provider PROVIDER \
  --documentation docs/my-provider.md
```

Both commands default to the current UTC time; `--asof` permits explicit historical replay. Daily generation rejects stale data, fits Ridge using matured labels, and persists pending signals. Settlement replays the account through C++, stores fills/account states transactionally, and rejects revisions to recorded historical account events.

The bundled Yahoo downloader stops at December 2025, so that fixed snapshot cannot support current daily operation. Fresh imports are operator-provided. The daily Ridge refit is a separate paper workflow from the six-month research refit schedule. Completed-session settlement simulates the saved eligible open retrospectively; it is not evidence of an actual open fill.

## Testing and reproducibility

```sh
make test
```

The latest local verification passed **34 pytest tests** and **1 CTest suite**. Checks include:

- Forward-label alignment, future-price perturbation, chronological fold purity, and training-only scaling.
- Hand-calculated and independent Python/C++ accounting comparisons.
- No-trade, known-return, fee-only, slippage-only, cash-limit, missing-price, and malformed-contract cases.
- Normalized corporate-action conventions and consistent Yahoo OHLC adjustment.
- Daily freshness checks and restart-safe replay/settlement.

All 34,208 imported OHLC rows matched `yfinance`'s adjustment calculation within `1e-12` relative/absolute tolerance. Historical output hashes were verified, and all five base accounts had nonnegative cash, no stale marks, and reconciled per-symbol attribution. The original synthetic verification also reproduced 78,480 forecasts/weights and 100 C++ output tables exactly across independent runs; that is a synthetic reproducibility result, not a claim of independent historical-data replication.

Seeds and dependencies are pinned. Manifests record source, input, configuration, and model hashes, package versions, machine information, and measured runtime. [GitHub Actions](.github/workflows/ci.yml) defines offline tests, C++ build, and a synthetic smoke run after dependency installation; no live data endpoint is required by CI.

## Command reference

| Command | Purpose |
|---|---|
| `make setup` | Create `.venv` and install pinned dependencies |
| `make data` | Generate and validate the synthetic research store |
| `make build` | Build the C++ simulator with CMake |
| `make test` | Run pytest and CTest |
| `make demo RUN=<new-name>` | Run the complete synthetic workflow |
| `make research CONFIG=configs/base.yaml RUN=<new-name>` | Run the synthetic workflow with the specified configuration |
| `make report RUN=<existing-name>` | Regenerate a saved run's report |

Real-data selection uses the `research.run` CLI with `--raw`, `--provider`, and `--documentation`; `make research` does not select real data automatically.

## Repository layout

```text
research/       Data store, Yahoo download, features, splits, models, weights, exports, pipeline
simulator/      C++17 execution and accounting engine
paper/          SQLite replay, daily signal generation, and settlement
reporting/      Metrics, diagnostics, plots, and Markdown report generation
configs/        Frozen experiment settings
tests/          Python integrity checks and independent simulator fixtures
docs/           Protocol, provenance, contracts, and implementation notes
data/           Local provider snapshots, normalized imports, and caches
results/        Selected saved outputs from the Yahoo Finance run
artifacts/      Generated run manifests, models, reports, and ledgers
.github/        CI workflow
CMakeLists.txt  C++ build and CTest integration
Makefile        Setup, build, test, and research commands
```

## Limitations and next research step

Yahoo supplies a current-vintage historical snapshot. Later corporate actions and revisions can affect adjusted prices; absolute adjusted dollar-volume features and normalized share rounding are not guaranteed to be point-in-time. The simulator supports normalized-price accounting rather than raw prices with explicit split/dividend cash flows. No independent provider cross-check has yet been completed.

The universe contains eight retrospectively selected surviving ETFs. Execution costs are assumptions, open fills omit market impact and actual liquidity constraints, and the cross-sectional IC uses a small universe. Bootstrap intervals and a retrospective holdout do not establish alpha or remove regime and selection uncertainty. There is no accumulated prospective live trading history.

The next justified step is independent-provider validation and point-in-time corporate-action accounting under a newly documented protocol, before making stronger performance claims. Preserve the current results and avoid tuning against the already-observed 2024–2025 holdout.

Further reading: [research protocol](docs/protocol.md), [Yahoo provenance](docs/yahoo-data.md), [data requirements](docs/data.md), and [signal/accounting contracts](docs/contracts.md).
