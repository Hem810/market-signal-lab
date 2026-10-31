"""Settle saved pending paper signals using newly completed imported sessions.
Replay the complete account through the actual C++ engine; persist only new events.
"""

import argparse, json, sqlite3, subprocess
from pathlib import Path
import pandas as pd
from research.store import ingest, calendar
from research.export import signals, market


def settle(ledger, raw, asof, provider, documentation, output):
    now = pd.Timestamp(asof)
    if now.tzinfo is None:
        raise ValueError("Timezone required")
    out = Path(output)
    out.mkdir(parents=True, exist_ok=True)
    d = ingest(raw, out / "store", provider, documentation)
    cal = calendar(str(d.session.min().date()), str(d.session.max().date()))
    d = d[d.session.map(cal["close"]) <= now]  # no partial-day close leakage
    c = sqlite3.connect(ledger)
    records = [
        json.loads(x[0]) for x in c.execute("SELECT payload FROM pending ORDER BY eligible,symbol")
    ]
    if not records:
        c.close()
        return 0
    s = pd.DataFrame(records)
    for k in ["signal_ts", "entry_ts"]:
        s[k] = pd.to_datetime(s[k], utc=True)
    s = s[s.entry_ts <= now]
    if s.empty or d.empty:
        c.close()
        return 0
    signals(s, out / "signals.csv", "paper")
    market(d, out / "market.csv")
    subprocess.run(
        [
            "build/market_sim",
            str(out / "signals.csv"),
            str(out / "market.csv"),
            str(out / "account"),
            "1",
            "5",
            "100000",
        ],
        check=True,
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS settlements(id TEXT PRIMARY KEY, kind TEXT, payload TEXT)"
    )
    n = 0
    with c:
        for kind, path in [("fill", "account-fills.csv"), ("account", "account-equity.csv")]:
            for row in pd.read_csv(out / path).to_dict("records"):
                if kind == "fill" and row["status"] == "unavailable_session":
                    continue
                key = kind + ":" + row["session"] + ":" + str(row.get("symbol", "portfolio"))
                payload = json.dumps(row, sort_keys=True)
                old = c.execute("SELECT payload FROM settlements WHERE id=?", (key,)).fetchone()
                if old and old[0] != payload:
                    raise ValueError("Historical account revision; manual review required")
                c.execute("INSERT OR IGNORE INTO settlements VALUES(?,?,?)", (key, kind, payload))
                n += 1
        latest = pd.read_csv(out / "account-equity.csv")
        if len(latest):
            for row in s.to_dict("records"):
                if row["entry_ts"].strftime("%Y-%m-%d") <= latest.session.max():
                    c.execute(
                        "UPDATE pending SET state='processed' WHERE symbol=? AND eligible=?",
                        (row["symbol"], row["entry_ts"].isoformat()),
                    )
    c.close()
    return n


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ledger", default="artifacts/daily/paper.sqlite")
    p.add_argument("--raw", required=True)
    p.add_argument("--asof", default=pd.Timestamp.now(tz="UTC").isoformat())
    p.add_argument("--provider", required=True)
    p.add_argument("--documentation")
    p.add_argument("--output", default="artifacts/daily/settlement")
    a = p.parse_args()
    print(settle(a.ledger, a.raw, a.asof, a.provider, a.documentation, a.output))
