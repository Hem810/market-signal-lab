"""Idempotent, transactional historical replay ledger. No broker connectivity."""

import hashlib, json, sqlite3
from pathlib import Path
import pandas as pd


def connect(path):
    c = sqlite3.connect(path)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        "CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, kind TEXT, eligible TEXT, payload TEXT)"
    )
    return c


def replay(path, signals, equity, fills, asof, run_hash, stop_after=None):
    c = connect(path)
    n = 0
    asof = pd.Timestamp(asof)
    if asof.tzinfo is None:
        asof = asof.tz_localize("UTC")
    batches = [
        ("signal", signals, "signal_ts"),
        ("fill", fills, "execution_ts"),
        ("account", equity, "session"),
    ]
    for kind, frame, col in batches:
        for row in frame.to_dict("records"):
            t = pd.Timestamp(row[col])
            t = t.tz_localize("UTC") if t.tzinfo is None else t
            if kind == "account":
                t = t + pd.Timedelta(hours=23, minutes=59)
            if t > asof:
                continue
            payload = json.dumps(
                dict(row, run_hash=run_hash, mode="historical_replay"), sort_keys=True, default=str
            )
            key = hashlib.sha256(payload.encode()).hexdigest()
            c.execute(
                "INSERT OR IGNORE INTO events VALUES(?,?,?,?)", (key, kind, t.isoformat(), payload)
            )
            n += 1
            if n % 1000 == 0:
                c.commit()
            if stop_after and n == stop_after:
                c.commit()
                c.close()
                raise InterruptedError("deliberate restart fixture")
    c.commit()
    result = c.execute("SELECT count(*) FROM events").fetchone()[0]
    c.close()
    return result


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--run", required=True)
    p.add_argument("--asof", required=True)
    a = p.parse_args()
    r = Path(a.run)
    print(
        replay(
            r / "paper.sqlite",
            pd.read_csv(r / "ridge-signals.csv"),
            pd.read_csv(r / "ridge-base-equity.csv"),
            pd.read_csv(r / "ridge-base-fills.csv"),
            a.asof,
            hashlib.sha256((r / "ledger_manifest.json").read_bytes()).hexdigest(),
        )
    )
