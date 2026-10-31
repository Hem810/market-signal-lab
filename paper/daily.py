"""Manual completed-session import → causal model fit → durable pending signals.
Only operator-imported CSVs are used; no endpoint or broker is contacted.
"""

import argparse, hashlib, json, pickle, sqlite3
from pathlib import Path
import pandas as pd
from research.store import ingest, calendar, digest
from research.features import engineer, FEATURES
from research.models import estimator
from research.splits import inner
from research.portfolio import weights
from research.export import signals


def daily(raw, ledger, asof, provider, documentation, output):
    now = pd.Timestamp(asof)
    if now.tzinfo is None:
        raise ValueError("asof must specify timezone")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Filter at the provider boundary before normalization/features.
    cutoff = now.tz_convert("America/New_York").date()
    schedule = calendar(
        str(pd.Timestamp(cutoff) - pd.Timedelta(days=30)),
        str(pd.Timestamp(cutoff) + pd.Timedelta(days=14)),
    )
    eligible = schedule[schedule["close"] + pd.Timedelta(minutes=1) <= now]
    if eligible.empty:
        raise ValueError("No completed eligible session")
    last = eligible.index[-1]
    snapshot = output / last.strftime("%Y-%m-%d")
    snapshot.mkdir(exist_ok=True)
    filtered = snapshot / "raw"
    filtered.mkdir(exist_ok=True)
    for path in sorted(Path(raw).glob("*.csv")):
        g = pd.read_csv(path)
        g.columns = g.columns.str.lower()
        g = g.rename(columns={"date": "session"})
        g = g[pd.to_datetime(g.session) <= last]
        dest = filtered / path.name
        payload = g.to_csv(index=False)
        if dest.exists() and dest.read_text() != payload:
            raise ValueError("Historical data revised: review in a new ledger before proceeding")
        if not dest.exists():
            dest.write_text(payload)
    d = ingest(filtered, snapshot / "store", provider, documentation)
    if any(g.session.max() != last for _, g in d.groupby("symbol")):
        raise ValueError("Stale/missing latest completed session")
    f = engineer(d)
    row = f[f.session == last].dropna(subset=FEATURES)
    if len(row) != 8:
        raise ValueError("Require all eight eligible universe symbols")
    train = f[
        (f.label_end < now)
        & (f.signal_ts < row.signal_ts.min())
        & (f.session >= pd.Timestamp("2010-01-01"))
    ].dropna(subset=FEATURES + ["target"])
    if train.session.nunique() < 750:
        raise ValueError("Insufficient three-year training history")
    a, b, _ = inner(train)
    scores = []
    for alpha in [1.0, 100.0]:
        m = estimator("ridge", alpha).fit(a[FEATURES], a.target)
        scores.append((((m.predict(b[FEATURES]) - b.target) ** 2).mean(), alpha))
    m = estimator("ridge", min(scores)[1]).fit(train[FEATURES], train.target)
    row = row.copy()
    row["prediction"] = m.predict(row[FEATURES])
    row = weights(row)
    row["model"] = "ridge"
    row["fold"] = "daily-" + last.strftime("%Y-%m-%d")
    # Actual creation after the close may occur after next open: never backdate.
    future = schedule[schedule.open > now]
    if future.empty:
        raise ValueError("No eligible next session")
    row["signal_ts"] = now
    row["entry_ts"] = future.open.iloc[0]
    modelbytes = pickle.dumps(m)
    modelhash = hashlib.sha256(modelbytes).hexdigest()
    config_hash = digest("configs/base.yaml")
    ledger = Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(ledger)
    c.execute(
        "CREATE TABLE IF NOT EXISTS pending(id TEXT PRIMARY KEY, session TEXT, symbol TEXT, created TEXT, eligible TEXT, model_hash TEXT, config_hash TEXT, state TEXT, payload TEXT, UNIQUE(session,symbol))"
    )
    with c:
        for record in row[
            [
                "symbol",
                "signal_ts",
                "entry_ts",
                "prediction",
                "weight",
                "volatility",
                "model",
                "fold",
            ]
        ].to_dict("records"):
            key = hashlib.sha256(
                (str(last.date()) + record["symbol"] + config_hash).encode()
            ).hexdigest()
            old = c.execute(
                "SELECT config_hash,model_hash FROM pending WHERE session=? AND symbol=?",
                (str(last.date()), record["symbol"]),
            ).fetchone()
            if old and old != (config_hash, modelhash):
                raise ValueError("Existing session configuration/model conflict")
            c.execute(
                "INSERT OR IGNORE INTO pending VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    key,
                    str(last.date()),
                    record["symbol"],
                    now.isoformat(),
                    record["entry_ts"].isoformat(),
                    modelhash,
                    config_hash,
                    "pending",
                    json.dumps(record, default=str, sort_keys=True),
                ),
            )
    # Export durable original creation timestamps, not rerun wall-clock values.
    saved = [
        json.loads(x[0])
        for x in c.execute(
            "SELECT payload FROM pending WHERE session=? ORDER BY symbol", (str(last.date()),)
        )
    ]
    c.close()
    saved = pd.DataFrame(saved)
    for col in ["signal_ts", "entry_ts"]:
        saved[col] = pd.to_datetime(saved[col], utc=True)
    signals(saved, snapshot / "signals.csv", "paper")
    (snapshot / "model.pkl").write_bytes(modelbytes)
    (snapshot / "manifest.json").write_text(
        json.dumps(
            dict(
                model_hash=modelhash,
                config_hash=config_hash,
                latest_training_information=str(train.label_end.max()),
                mode="imported_completed_sessions",
                provider=provider,
            ),
            indent=2,
        )
    )
    return snapshot / "signals.csv"


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--raw", required=True)
    p.add_argument("--ledger", default="artifacts/daily/paper.sqlite")
    p.add_argument("--asof", default=pd.Timestamp.now(tz="UTC").isoformat())
    p.add_argument("--provider", required=True)
    p.add_argument("--documentation")
    p.add_argument("--output", default="artifacts/daily")
    a = p.parse_args()
    print(daily(a.raw, a.ledger, a.asof, a.provider, a.documentation, a.output))
