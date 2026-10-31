import numpy as np
import pandas as pd
from research.store import calendar

FEATURES = ["ret1", "ret5", "ret20", "ret60", "distance", "volatility", "range", "liquidity"]


def engineer(data):
    cal = calendar(
        str(data.session.min().date()), str((data.session.max() + pd.Timedelta(days=15)).date())
    )
    result = []
    for sym, g in data.groupby("symbol"):
        g = g.set_index("session").reindex(cal.index).copy()
        g["symbol"] = sym
        for n in [1, 5, 20, 60]:
            g[f"ret{n}"] = g.close / g.close.shift(n) - 1
        g["distance"] = g.close / g.close.rolling(20).mean() - 1
        g["volatility"] = g.ret1.rolling(20).std()
        g["range"] = (g.high - g.low) / g.close
        g["liquidity"] = np.log((g.close * g.volume).rolling(20).mean())
        g["feature_ts"] = cal["close"]
        g["signal_ts"] = cal["close"] + pd.Timedelta(minutes=1)
        g["entry_ts"] = cal["open"].shift(-1)
        g["exit_ts"] = cal["open"].shift(-2)
        g["label_end"] = g.exit_ts
        g["target"] = g.open.shift(-2) / g.open.shift(-1) - 1
        g.index.name = "session"
        result.append(g.reset_index())
    return pd.concat(result).sort_values(["session", "symbol"]).reset_index(drop=True)
