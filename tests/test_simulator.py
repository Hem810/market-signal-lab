import os, subprocess
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from tests.reference import reference
from research.export import SIGNAL_HEADER, MARKET_HEADER

BIN = os.environ.get("MARKET_SIM", str(Path("build/market_sim").resolve()))


def fixture(tmp_path, prices, weights, fee=0, slip=0, capital=1000):
    ss = []
    mm = []
    for i, ((op, cl), w) in enumerate(zip(prices, weights), start=2):
        dt = f"2020-01-{i:02}"
        prev = f"2020-01-{i-1:02}"
        if w is not None:
            ss.append(
                [
                    1,
                    "test",
                    "rule",
                    "fold",
                    "SPY",
                    prev + "T21:01:00Z",
                    dt + "T14:30:00Z",
                    0.01,
                    w,
                    0.1,
                ]
            )
        mm.append([dt, dt + "T14:30:00Z", dt + "T21:00:00Z", "SPY", op, cl])
    s = tmp_path / "s.csv"
    m = tmp_path / "m.csv"
    pd.DataFrame(ss, columns=SIGNAL_HEADER.split(",")).to_csv(s, index=False)
    pd.DataFrame(mm, columns=MARKET_HEADER.split(",")).to_csv(m, index=False)
    cmd = [
        BIN,
        str(s),
        str(m),
        str(tmp_path / "out"),
        str(fee * 10000),
        str(slip * 10000),
        str(capital),
    ]
    return cmd, s, m


@pytest.mark.parametrize(
    "prices,weights,fee,slip",
    [
        ([(100, 100)] * 3, [0, 0, 0], 0, 0),
        ([(100, 100)] * 3, [0.25, None, 0], 0, 0),
        ([(100, 110), (120, 125), (130, 130)], [0.25, None, 0], 0, 0),
        ([(100, 100)] * 3, [0.25, None, 0], 0.001, 0),
        ([(100, 100)] * 3, [0.25, None, 0], 0, 0.002),
        ([(100, 100)] * 3, [0.25, 0.25, 0], 0.9, 0),
    ],
)
def test_reference(tmp_path, prices, weights, fee, slip):
    cmd, _, _ = fixture(tmp_path, prices, weights, fee, slip)
    subprocess.run(cmd, check=True)
    e = pd.read_csv(tmp_path / "out-equity.csv")
    np.testing.assert_allclose(e.equity, reference(prices, weights, fee=fee, slip=slip), atol=1e-8)
    assert e.cash.min() >= 0 and e.residual.abs().max() < 1e-8
    a = pd.read_csv(tmp_path / "out-attribution.csv")
    np.testing.assert_allclose(
        a.groupby("session").pnl.sum(), e.equity.diff().fillna(e.equity.iloc[0] - 1000), atol=1e-8
    )


@pytest.mark.parametrize("mutation", ["duplicate", "early", "schema", "nan", "leverage"])
def test_bad_contract(tmp_path, mutation):
    cmd, s, _ = fixture(tmp_path, [(100, 100)], [0.25])
    d = pd.read_csv(s)
    if mutation == "duplicate":
        d = pd.concat([d, d])
    if mutation == "early":
        d["entry_ts"] = d.signal_ts
    if mutation == "schema":
        d = d.drop(columns="fold")
    if mutation == "nan":
        d["prediction"] = "nan"
    if mutation == "leverage":
        d["weight"] = 1.5
    d.to_csv(s, index=False)
    assert subprocess.run(cmd, capture_output=True).returncode != 0


def test_missing_symbol(tmp_path):
    cmd, _, m = fixture(tmp_path, [(100, 100)], [0.25])
    d = pd.read_csv(m)
    d["symbol"] = "QQQ"
    d.to_csv(m, index=False)
    subprocess.run(cmd, check=True)
    f = pd.read_csv(tmp_path / "out-fills.csv")
    assert f.status.iloc[0] == "missing_open"


def test_normalized_split_fixture(tmp_path):
    # A consistently adjusted 2:1 split remains continuous, no second split action.
    cmd, _, _ = fixture(tmp_path, [(50, 50)] * 3, [0.25, None, 0])
    subprocess.run(cmd, check=True)
    assert (pd.read_csv(tmp_path / "out-equity.csv").equity == 1000).all()


def test_cash_limit_multiple_symbols(tmp_path):
    cmd, s, m = fixture(tmp_path, [(100, 100)], [0.25], 0.01, 0.01)
    sd = pd.read_csv(s)
    md = pd.read_csv(m)
    pd.concat([sd.assign(symbol=x) for x in ["A", "B", "C", "D"]]).to_csv(s, index=False)
    pd.concat([md.assign(symbol=x) for x in ["A", "B", "C", "D"]]).to_csv(m, index=False)
    cmd[-1] = "800"
    subprocess.run(cmd, check=True)
    e = pd.read_csv(tmp_path / "out-equity.csv")
    f = pd.read_csv(tmp_path / "out-fills.csv")
    assert e.cash.iloc[0] >= 0 and (f.status == "cash_limited").any()


def test_stale_holding_and_missing_session(tmp_path):
    cmd, s, m = fixture(tmp_path, [(100, 100), (110, 110), (120, 120)], [0.25, 0.25, 0])
    d = pd.read_csv(m)
    d.loc[1, "symbol"] = "QQQ"
    d.to_csv(m, index=False)
    subprocess.run(cmd, check=True)
    e = pd.read_csv(tmp_path / "out-equity.csv")
    assert e.stale.iloc[1] == 1 and e.equity.iloc[1] == 1000
    d = d.iloc[:2]
    d.to_csv(m, index=False)
    subprocess.run(cmd, check=True)
    assert "unavailable_session" in pd.read_csv(tmp_path / "out-fills.csv").status.tolist()
