"""Validated normalized-price store. Raw imports are never modified."""

import hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import exchange_calendars as xc

SYMBOLS = ["SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "GLD", "XLE"]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def calendar(start, end):
    c = xc.get_calendar("XNYS", start=start, end=end)
    s = c.schedule.loc[start:end].copy()
    s.index = pd.to_datetime(s.index).tz_localize(None)
    return s


def validate(df):
    required = ["symbol", "session", "open", "high", "low", "close", "volume"]
    if not set(required) <= set(df):
        raise ValueError("missing schema columns")
    d = df.copy()
    d["session"] = pd.to_datetime(d.session)
    if d[required].isna().any().any() or d.duplicated(["symbol", "session"]).any():
        raise ValueError("null or duplicate")
    for k in required[2:]:
        d[k] = pd.to_numeric(d[k], errors="raise")
    if not np.isfinite(d[required[2:]]).all().all():
        raise ValueError("nonfinite")
    if (d[["open", "high", "low", "close"]] <= 0).any().any() or (d.volume <= 0).any():
        raise ValueError("nonpositive price/volume")
    if (
        (d.high < d[["open", "close", "low"]].max(axis=1))
        | (d.low > d[["open", "close", "high"]].min(axis=1))
    ).any():
        raise ValueError("invalid OHLC")
    cal = calendar(str(d.session.min().date()), str(d.session.max().date()))
    findings = {}
    for sym, g in d.groupby("symbol"):
        expected = cal.loc[g.session.min() : g.session.max()].index
        if not g.session.isin(cal.index).all():
            raise ValueError("non-session observations")
        findings[sym] = {
            "missing_sessions": [str(x.date()) for x in expected.difference(g.session)],
            "discontinuities": int((g.sort_values("session").close.pct_change().abs() > 0.4).sum()),
            "start": str(g.session.min().date()),
            "end": str(g.session.max().date()),
        }
    return d.sort_values(["session", "symbol"]).reset_index(drop=True), findings


def synthetic(out, start="2009-01-01", end="2025-12-31", seed=1729):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    dates = calendar(start, end).index
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 0.007, len(dates))
    rows = []
    for i, s in enumerate(SYMBOLS):
        close = (50 + i * 15) * np.exp(
            np.cumsum(0.0001 + common * 0.5 + rng.normal(0, 0.008, len(dates)))
        )
        op = np.r_[close[0], close[:-1]] * np.exp(rng.normal(0, 0.003, len(dates)))
        g = pd.DataFrame(
            dict(
                symbol=s,
                session=dates,
                open=op,
                high=np.maximum(op, close) * 1.005,
                low=np.minimum(op, close) * 0.995,
                close=close,
                volume=rng.integers(1000000, 9000000, len(dates)),
            )
        )
        p = out / f"{s}.csv"
        if not p.exists():
            g.to_csv(p, index=False)
        rows.append(p)
    return rows


def ingest(raw, dest, provider="synthetic", documentation=None):
    if provider != "synthetic" and (not documentation or not Path(documentation).is_file()):
        raise ValueError("Real imports require a provider adjustment documentation file")
    paths = sorted(Path(raw).glob("*.csv"))
    frames = []
    for p in paths:
        d = pd.read_csv(p)
        d.columns = d.columns.str.lower()
        d = d.rename(columns={"date": "session"})
        if "symbol" not in d:
            d["symbol"] = p.stem
        frames.append(d)
    d, findings = validate(pd.concat(frames, ignore_index=True))
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    d.to_parquet(dest / "market.parquet", index=False)
    meta = dict(
        provider=provider,
        synthetic=provider == "synthetic",
        adjustment="consistent adjusted OHLC; normalized shares; no separate distributions",
        currency="USD",
        calendar="XNYS",
        timezone="America/New_York",
        imported_at=pd.Timestamp.now(tz="UTC").isoformat(),
        raw_hashes={str(p): digest(p) for p in paths},
        findings=findings,
        documentation=documentation,
        documentation_hash=digest(documentation) if documentation else None,
    )
    (dest / "metadata.json").write_text(json.dumps(meta, indent=2))
    return d


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--raw", default="data/raw/synthetic")
    p.add_argument("--dest", default="data/processed/synthetic")
    p.add_argument("--synthetic", action="store_true")
    p.add_argument("--provider", default="synthetic")
    p.add_argument("--documentation")
    a = p.parse_args()
    if a.synthetic:
        synthetic(a.raw)
    ingest(a.raw, a.dest, a.provider, a.documentation)
