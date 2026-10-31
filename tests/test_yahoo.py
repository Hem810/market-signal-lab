import numpy as np
import pandas as pd
import pytest
from research.download_yahoo import normalize


def test_adjustment_applies_to_all_prices_once():
    d = pd.DataFrame(
        {
            "Open": [100.0, 102.0],
            "High": [110.0, 112.0],
            "Low": [90.0, 92.0],
            "Close": [105.0, 108.0],
            "Adj Close": [52.5, 54.0],
            "Volume": [1000, 2000],
        },
        index=pd.date_range("2020-01-02", periods=2, tz="America/New_York"),
    )
    n = normalize(d, "SPY")
    np.testing.assert_allclose(
        n[["open", "high", "low", "close"]], d[["Open", "High", "Low", "Close"]].to_numpy() * 0.5
    )
    np.testing.assert_array_equal(n.volume, d.Volume)
    assert n.session.iloc[0] == pd.Timestamp("2020-01-02")


def test_bad_adjustment_rejected():
    d = pd.DataFrame({"Close": [10.0], "Adj Close": [float("nan")]})
    with pytest.raises(ValueError, match="adjustment"):
        normalize(d, "SPY")
