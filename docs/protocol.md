# Frozen protocol (before experiments)
Pipeline stages: store → timing/features → folds → models/weights → contracts → C++ account → execution fixtures → SQLite replay → report → integration.

Seed 1729. Fixed ETF universe SPY QQQ IWM EFA EEM TLT GLD XLE, selected for broad asset-class coverage, not performance. Retrospective surviving ETFs cannot measure survivorship bias. Requested real scope 2010–2025; 2009 warm-up only. Development OOS 2013–2023; final 2024–2025. Six-month expanding refits, three-year initial history. Final outcomes cannot change choices. Inner validation is last six months of matured training labels. Ridge alpha {1,100}; boosting {15,31} leaves, 50 iterations, learning rate .05. Lowest inner MSE wins. No threshold search.

Momentum forecast = trailing 20-session return / 20. All candidates: positive predictions ranked descending, alphabetical ties; top four receive 24% each, others zero; unused capacity is cash. 24% targets leave cost buffer below 25% trade-time cap. Price drift can exceed cap between trades. Initial capital $100,000; integer shares; daily open rebalance; zero cash interest. Equal-weight benchmark buys once and holds (drift explicitly allowed); cash benchmark earns zero. Terminal positions marked, not liquidated.

|Event|Time|
|---|---|
|Features available|session t close|
|Signal|close t + 1 minute|
|First fill|open t+1|
|Label ends|open t+2|

Target open[t+2]/open[t+1]-1; training labels strictly before fit cutoff. XNYS calendar, America/New_York sessions; contracts UTC ISO strings. Nasdaq ETF sessions use common US calendar approximation. No forward filling inputs. Missing current open rejects trade; held inventory carries last mark, flagged stale. Full-day volume is never used to authorize open fills. Zero-volume daily records are rejected in validation, not used as clairvoyant open liquidity checks.

Only consistently adjusted OHLC imports accepted: normalized-share approximation, no separate dividends/splits, no claim of executable historical share counts. Real provider adjustment documentation must be supplied with imports. No mixed raw open/adjusted close. Synthetic fixtures have no corporate actions. Base commission 1bp and adverse slippage 5bp charged explicitly once on reference open notional; 0/.5/1/2 cost multiples and one-session delay. Gross is a separate zero-cost account (cash/rounding may differ).

Daily close equity decomposition: prior inventory overnight change + post-trade inventory intraday change - fees - slippage. No liquidation at boundaries; returns within final holdout include inherited holdings. Diagnostics never select models on final period. Moving-block bootstrap: 20 sessions, 200 draws; uncertainty descriptive, no alpha conclusion from synthetic data.

Real-data retrieval failure permits synthetic completion only; market profitability, actual coverage and empirical alpha remain unmeasured. TWAP/VWAP only deterministic synthetic intraday experiments, fixed prior profile, completed-bar fills with residual cancellation. Paper replay is historical simulation, never a live record.
