# Data requirements and provenance

## Historical market data

The Yahoo Finance snapshot contains all eight ETFs over 2009–2025, with complete expected XNYS session coverage. See [Yahoo provenance](yahoo-data.md) for issuer inception sources, download parameters, adjustment methodology, checksums, and current-vintage limitations.

Each run stores the normalized Parquet table and metadata describing the provider, input hashes, actual coverage, gaps, discontinuities, adjustment convention, currency, calendar, and timezone. Provider-returned files are preserved separately from normalized imports.

## Synthetic fixtures

The offline demo generates seeded synthetic OHLCV on the XNYS calendar over 2009–2025, with 2009 reserved for feature warm-up. These observations are not ETF price history. Existing fixture files are reused; use a separate directory when generating a different dataset.

## Import contract

Provide per-symbol CSV files with `session` (or `date`), `open`, `high`, `low`, `close`, and `volume`. A `symbol` column is optional when the filename identifies the ETF. The research pipeline requires the fixed eight-symbol universe.

Real imports require a provider name and a provenance document describing source URLs, download time, adjustment conventions, inception dates, coverage, and known limitations. Use consistently adjusted OHLC. Raw-price accounting with explicit corporate-action cash flows is unsupported; do not combine adjusted close with incompatible raw opens or add distributions twice.

Validation checks required fields, finite numeric values, duplicate symbol-session keys, nonpositive prices/volume, OHLC relationships, exchange-session membership, missing sessions, and large price discontinuities. Missing observations are never backfilled. Close-to-close moves above 40% are flagged for investigation rather than automatically repaired.

## Calendar and availability

Session timestamps and early closes come from the pinned exchange-calendars XNYS schedule. Common US ETF sessions use that calendar approximation even when listing venues differ. Contracts use UTC; exchange-session dates follow America/New_York.

Zero-volume daily rows fail offline input validation. Completed daily volume is never passed to the next-open simulator as an open-time liquidity signal. This retrospective quality filtering must be disclosed when interpreting historical performance.

## Research limitations

Current-vintage adjusted history can include later revisions and corporate actions. It is not a point-in-time archive. Absolute adjusted dollar-volume features and normalized share rounding can depend on those adjustments. No independent-provider replication has been completed. Synthetic data validates engineering behavior only; historical simulations do not establish actual execution quality or profitable alpha.
