# Contracts v1
UTF-8 CSV without quoted commas; exact header and column order; UTC `YYYY-MM-DDTHH:MM:SSZ`, chronological entry then alphabetical symbol. Symbols and IDs must not contain commas/newlines. All numeric fields finite decimal; absent prices are absent market rows, never zero/NaN. Duplicate (entry,symbol) signals and (session,symbol) market rows rejected. One model/run per file. Market file must contain complete session coverage; partial held-symbol bars produce stale-mark flags. Signals for absent sessions produce explicit unfilled status.

Signal header: `version,run,model,fold,symbol,signal_ts,entry_ts,prediction,weight,volatility`

Example: `1,demo,ridge,2013-01,SPY,2013-01-02T21:01:00Z,2013-01-03T14:30:00Z,0.001,0.24,0.01`

version integer 1; identifiers strings; prediction decimal holding-period return; weight fraction of pretrade open equity (0–.25); volatility trailing daily return standard deviation. Signal has no target/realized return. Risk input is descriptive, not a fill trigger.

Market header: `session,open_ts,close_ts,symbol,open,close`. Session is ISO exchange date; prices positive USD consistently adjusted normalized prices. No dividend or split flows: adjustment already incorporates them. Historical fractional economic units are rounded to integer normalized shares, an approximation to tradable shares. No inference of intraday volume or liquidity from daily bars. Sizing occurs at open from open equity, selling before buying, alphabetical tie order. Explicit fees and slippage reduce cash once; reported fill price is the reference open, not adverse adjusted price.

Position cap applies to target weights at rebalance. Drift after fills/overnight and buy-and-hold benchmark can exceed 25%; this is not a continuously enforced risk limit. Stale marks forbid trading affected symbol. New instruments need 60 observed calendar sessions of valid features; missing periods yield invalid features, never backfill. A delisted/missing held asset is carried at last known mark and flags empirical invalidity; this is not a liquidation assumption.

Outputs: equity/cash/exposure and daily attribution; fills include requested vs filled shares and status; positions are close marks. Overnight = prior shares × (current open − prior close); intraday = posttrade shares × (current close − current open). Per-symbol fees/slippage sum to portfolio. Cash + close market value = equity; change = overnight + intraday − fees − slippage. Tolerance 1e-6 dollars per $100,000 equity. Gross account replays sizing independently with zero costs.
