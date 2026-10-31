import pandas as pd

SIGNAL_HEADER = "version,run,model,fold,symbol,signal_ts,entry_ts,prediction,weight,volatility"
MARKET_HEADER = "session,open_ts,close_ts,symbol,open,close"


def iso(s):
    return pd.to_datetime(s, utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def signals(d, path, run):
    g = d.copy()
    g["version"] = 1
    g["run"] = run
    assert not g.duplicated(["entry_ts", "symbol"]).any()
    assert (g.entry_ts > g.signal_ts).all() and g.weight.between(0, 0.25).all()
    assert (g.groupby("entry_ts").weight.sum() <= 1 + 1e-12).all()
    for k in ["signal_ts", "entry_ts"]:
        g[k] = iso(g[k])
    g.sort_values(["entry_ts", "symbol"])[SIGNAL_HEADER.split(",")].to_csv(path, index=False)


def market(d, path):
    from research.store import calendar

    c = calendar(str(d.session.min().date()), str(d.session.max().date()))
    g = d.copy()
    g["open_ts"] = iso(g.session.map(c.open))
    g["close_ts"] = iso(g.session.map(c.close))
    g["session"] = g.session.dt.strftime("%Y-%m-%d")
    g.sort_values(["session", "symbol"])[MARKET_HEADER.split(",")].to_csv(path, index=False)
