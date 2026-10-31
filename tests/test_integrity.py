import sqlite3
import numpy as np
import pandas as pd
import pytest
from research.store import synthetic, ingest, validate
from research.features import engineer, FEATURES
from research.splits import folds, inner
from research.models import estimator
from research.portfolio import weights
from research.execution import execute
from paper.loop import replay


@pytest.fixture(scope="module")
def panel(tmp_path_factory):
    p = tmp_path_factory.mktemp("store")
    synthetic(p / "raw", end="2014-01-15")
    return ingest(p / "raw", p / "store")


def test_forward_label(panel):
    f = engineer(panel)
    s = f[f.symbol == "SPY"].reset_index(drop=True)
    i = 80
    assert s.target.iloc[i] == pytest.approx(s.open.iloc[i + 2] / s.open.iloc[i + 1] - 1)
    assert s.feature_ts.iloc[i] < s.signal_ts.iloc[i] < s.entry_ts.iloc[i] < s.label_end.iloc[i]


def test_future_invariance(panel):
    cut = pd.Timestamp("2013-07-01")
    changed = panel.copy()
    mask = changed.session > cut
    changed.loc[mask, ["open", "high", "low", "close"]] *= 2
    a = engineer(panel)
    b = engineer(changed)
    np.testing.assert_allclose(
        a.loc[a.session <= cut, FEATURES], b.loc[b.session <= cut, FEATURES], equal_nan=True
    )
    aa = a.dropna(subset=FEATURES + ["target"])
    bb = b.dropna(subset=FEATURES + ["target"])
    start, train, test = next(folds(aa))
    _, train2, test2 = next(folds(bb))
    assert train.label_end.max() < start
    pd.testing.assert_frame_equal(train, train2)
    for kind, param in [("ridge", 1), ("boost", 15)]:
        m = estimator(kind, param).fit(train[FEATURES], train.target)
        n = estimator(kind, param).fit(train2[FEATURES], train2.target)
        x = test[test.session <= cut]
        y = test2[test2.session <= cut]
        pred = m.predict(x[FEATURES])
        np.testing.assert_allclose(pred, n.predict(y[FEATURES]), atol=1e-14)
        x = x.copy()
        y = y.copy()
        x["prediction"] = pred
        y["prediction"] = n.predict(y[FEATURES])
        pd.testing.assert_series_equal(weights(x).weight, weights(y).weight)
        if kind == "ridge":
            np.testing.assert_allclose(m[0].mean_, train[FEATURES].mean(), atol=1e-12)


def test_folds(panel):
    f = engineer(panel).dropna(subset=FEATURES)
    seen = set()
    for cutoff, tr, te in folds(f):
        a, b, c = inner(tr)
        assert a.label_end.max() < b.signal_ts.min()
        assert tr.label_end.max() < cutoff
        keys = set(zip(te.symbol, te.signal_ts))
        assert not seen & keys
        seen |= keys
        assert te.groupby("session").symbol.nunique().eq(8).all()


def test_validation(panel):
    with pytest.raises(ValueError):
        validate(pd.concat([panel, panel.iloc[:1]]))
    for col, value in [("open", -1), ("volume", 0), ("high", 0.01)]:
        p = panel.copy()
        p.loc[0, col] = value
        with pytest.raises(ValueError):
            validate(p)
    _, findings = validate(panel.drop(index=panel.index[80]))
    assert sum(len(x["missing_sessions"]) for x in findings.values()) == 1


def test_intraday_causality():
    bars = [(100, 2000), (101, 3000), (102, 6000)]
    for k in ["immediate", "twap", "vwap"]:
        a = execute(1000, k, bars)
        b = execute(1000, k, bars[:2] + [(900, 1)])
        assert a["fills"][:2] == b["fills"][:2]
        assert a["filled"] + a["residual"] == 1000


def test_replay_restart(tmp_path):
    s = pd.DataFrame(
        [dict(signal_ts="2020-01-01T21:01:00Z", entry_ts="2020-01-02T14:30:00Z", symbol="SPY")]
    )
    e = pd.DataFrame([dict(session="2020-01-02", equity=1000)])
    f = pd.DataFrame([dict(execution_ts="2020-01-02T14:30:00Z", symbol="SPY", filled=1)])
    path = tmp_path / "ledger.sqlite"
    with pytest.raises(InterruptedError):
        replay(path, s, e, f, "2020-01-03T00:00:00Z", "hash", stop_after=1)
    assert replay(path, s, e, f, "2020-01-03T00:00:00Z", "hash") == 3
    assert replay(path, s, e, f, "2020-01-03T00:00:00Z", "hash") == 3
    assert replay(tmp_path / "early.sqlite", s, e, f, "2020-01-02T12:00:00Z", "hash") == 1


def test_daily_completed_session_and_idempotence(panel, tmp_path):
    from paper.daily import daily

    raw = tmp_path / "raw"
    raw.mkdir()
    for sym, g in panel.groupby("symbol"):
        g.to_csv(raw / f"{sym}.csv", index=False)
    args = (
        raw,
        tmp_path / "paper.sqlite",
        "2014-01-15T22:00:00Z",
        "synthetic",
        None,
        tmp_path / "daily",
    )
    path = daily(*args)
    first = path.read_bytes()
    daily(*args)
    assert path.read_bytes() == first
    d = pd.read_csv(path)
    assert (pd.to_datetime(d.entry_ts, utc=True) > pd.Timestamp(args[2])).all()
    conn = sqlite3.connect(tmp_path / "paper.sqlite")
    assert conn.execute("SELECT count(*) FROM pending").fetchone()[0] == 8
    conn.close()
    with pytest.raises(ValueError, match="Stale"):
        daily(
            raw,
            tmp_path / "other.sqlite",
            "2014-01-16T22:00:00Z",
            "synthetic",
            None,
            tmp_path / "other",
        )


def test_daily_settlement_restart(panel, tmp_path):
    from paper.daily import daily
    from paper.settle import settle

    raw = tmp_path / "raw"
    raw.mkdir()
    for sym, g in panel.groupby("symbol"):
        g.to_csv(raw / f"{sym}.csv", index=False)
    ledger = tmp_path / "paper.sqlite"
    daily(raw, ledger, "2014-01-13T22:00:00Z", "synthetic", None, tmp_path / "daily")
    n = settle(ledger, raw, "2014-01-15T22:00:00Z", "synthetic", None, tmp_path / "settled")
    assert n > 0
    assert settle(ledger, raw, "2014-01-15T22:00:00Z", "synthetic", None, tmp_path / "settled") == n
    c = sqlite3.connect(ledger)
    assert c.execute("SELECT count(*) FROM settlements").fetchone()[0] == n
    c.close()
