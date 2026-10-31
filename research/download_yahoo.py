"""Download immutable Yahoo snapshots and explicitly normalize all OHLC fields."""

import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
from research.store import SYMBOLS, calendar, digest, validate


def normalize(frame, symbol):
    ratio = frame["Adj Close"] / frame["Close"]
    if not np.isfinite(ratio).all() or (ratio <= 0).any():
        raise ValueError("Invalid adjustment factors")
    result = pd.DataFrame(index=frame.index)
    for col in ["Open", "High", "Low", "Close"]:
        result[col.lower()] = frame[col] * ratio
    result["volume"] = frame["Volume"]
    result["symbol"] = symbol
    result.index = (
        pd.to_datetime(result.index, utc=True)
        .tz_convert("America/New_York")
        .tz_localize(None)
        .normalize()
    )
    result.index.name = "session"
    return result.reset_index()


def download(output):
    root = Path(output)
    (root / "provider").mkdir(parents=True, exist_ok=True)
    (root / "normalized").mkdir(exist_ok=True)
    yf.set_tz_cache_location("data/cache/yfinance")
    yf.config.debug.hide_exceptions = False
    meta = {
        "provider": "Yahoo Finance via yfinance",
        "yfinance_version": yf.__version__,
        "requested_start": "2009-01-01",
        "requested_end_exclusive": "2026-01-01",
        "auto_adjust": False,
        "repair": False,
        "normalization": "OHLC multiplied by Adj Close / Close; volume unchanged; no additional dividend/split flows",
        "symbols": {},
        "failures": {},
    }
    all_frames = []
    for symbol in SYMBOLS:
        path = root / "provider" / f"{symbol}.csv"
        try:
            if path.exists():
                frame = pd.read_csv(path, index_col=0, parse_dates=True)
            else:
                frame = yf.Ticker(symbol).history(
                    start="2009-01-01",
                    end="2026-01-01",
                    auto_adjust=False,
                    actions=True,
                    repair=False,
                    timeout=30,
                )
                if frame.empty:
                    raise ValueError("Empty provider response")
                frame.to_csv(path)
            normalized = normalize(frame, symbol)
            normalized, findings = validate(normalized)
            expected = calendar("2009-01-01", "2025-12-31").index
            if set(normalized.session) != set(expected):
                raise ValueError("Incomplete requested exchange-session coverage")
            dest = root / "normalized" / f"{symbol}.csv"
            if not dest.exists():
                normalized.to_csv(dest, index=False)
            meta["symbols"][symbol] = {
                "rows": len(frame),
                "first_session": str(normalized.session.min().date()),
                "last_session": str(normalized.session.max().date()),
                "provider_sha256": digest(path),
                "normalized_sha256": digest(dest),
                "retrieved_at": pd.Timestamp(path.stat().st_mtime, unit="s", tz="UTC").isoformat(),
                "findings": findings[symbol],
                "split_events": int((frame.get("Stock Splits", pd.Series(dtype=float)) != 0).sum()),
                "dividend_events": int((frame.get("Dividends", pd.Series(dtype=float)) != 0).sum()),
            }
            all_frames.append(normalized)
            print(symbol, len(frame), "validated", flush=True)
        except Exception as exc:
            meta["failures"][symbol] = str(exc)
            print(symbol, type(exc).__name__, str(exc), flush=True)
        (root / "download_manifest.json").write_text(json.dumps(meta, indent=2))
    if meta["failures"]:
        raise RuntimeError("Download incomplete; see download_manifest.json")
    validate(pd.concat(all_frames, ignore_index=True))
    print("All eight histories validated.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="data/raw/yahoo-20261028")
    args = parser.parse_args()
    download(args.output)
