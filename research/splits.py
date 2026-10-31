import pandas as pd


def folds(d):
    for start in pd.date_range("2013-01-01", "2025-07-01", freq="6MS", tz="UTC"):
        end = start + pd.DateOffset(months=6)
        train = d[
            (d.session >= pd.Timestamp("2010-01-01"))
            & (d.signal_ts < start)
            & (d.label_end < start)
            & d.target.notna()
        ]
        test = d[(d.signal_ts >= start) & (d.signal_ts < end)]
        if len(train) and len(test):
            assert train.label_end.max() < test.signal_ts.min()
            yield start, train, test


def inner(train):
    cutoff = train.signal_ts.max() - pd.DateOffset(months=6)
    a = train[(train.signal_ts < cutoff) & (train.label_end < cutoff)]
    b = train[train.signal_ts >= cutoff]
    assert a.label_end.max() < b.signal_ts.min()
    return a, b, cutoff
