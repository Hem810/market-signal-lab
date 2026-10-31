# Yahoo Finance snapshot — 28 October 2026

Provider: Yahoo Finance through yfinance 1.2.0. Request: 2009-01-01 inclusive through 2026-01-01 exclusive, daily bars, actions=True, auto_adjust=False, repair=False. The downloader preserves provider-returned OHLC, adjusted close, volume, dividends and splits in `data/raw/yahoo-20261028/provider/`; these are library-returned tables, not raw HTTP responses. `download_manifest.json` records actual UTC retrieval timestamps and SHA-256 hashes. Provider OHLC is already split-adjusted; it is not an as-traded raw-price archive.

Normalized import files are in `data/raw/yahoo-20261028/normalized/`. Every OHLC field is multiplied by `Adj Close / Close` for that row; volume is unchanged. This is the same formula as the installed yfinance `utils.auto_adjust` implementation, inspected before downloading. Do not apply dividends or splits again in the simulator. Yahoo describes adjusted close as including splits and distributions: https://in.help.yahoo.com/kb/adjusted-close-sln28256.html . Library documentation: https://ranaroussi.github.io/yfinance/reference/api/yfinance.download.html .

All eight symbols have 4,276 observations from 2009-01-02 through 2025-12-31, matching every expected XNYS session. Validation found no missing sessions, duplicate keys, invalid OHLC, nonpositive prices/volume, or >40% close discontinuities. Total 34,208 symbol-session rows. Warm-up is 2009; estimation begins 2010; evaluation 2013–2025. No dates, models, hyperparameters, allocation rules or costs were changed for this import.

## Inception / first-trading coverage
Issuer product inception dates (all precede requested data):

|Symbol|Date|Issuer source|
|---|---|---|
|SPY|1993-01-22|https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-500-etf-trust-spy|
|QQQ|1999-03-10|https://www.invesco.com/us/en/financial-products/etfs/invesco-qqq-trust-series-1.html|
|IWM|2000-05-22|https://www.ishares.com/us/products/239710/ishares-russell-2000-etf|
|EFA|2001-08-14|https://www.blackrock.com/us/individual/products/investment-funds|
|EEM|2003-04-07|https://www.blackrock.com/us/individual/products/investment-funds|
|TLT|2002-07-22|https://www.blackrock.com/us/individual/products/investment-funds|
|GLD|2004-11-18|https://www.ssga.com/us/en/intermediary/etfs/spdr-gold-shares-gld|
|XLE|1998-12-16|https://www.ssga.com/us/en/individual/etfs/state-street-energy-select-sector-spdr-etf-xle|

These are issuer product dates, not necessarily trust formation or first trading dates. In particular GLD trust formation is 2004-11-12; the issuer's product date is 2004-11-18. Actual downloaded coverage is checked independently.

## Interpretation limits
This is a current-vintage historical snapshot, not a point-in-time archive. Adjusted prices may incorporate corporate actions and revisions learned after historical signal dates, including after the requested end date. Return-ratio features often cancel constant rescaling, but absolute adjusted dollar-volume, cross-sectional scale and normalized share rounding do not necessarily do so. Therefore this run is a preliminary normalized-price experiment, not a fully point-in-time, as-traded or deployable performance claim. No strategy retuning is permitted after viewing the holdout. The next validation should use independent data with point-in-time actions and actual cash/share accounting. No independent provider cross-check has yet been performed. Eight surviving ETFs retain retrospective universe-selection bias.
