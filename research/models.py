import json, pickle
import numpy as np
import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error
from research.features import FEATURES
from research.splits import folds, inner


def estimator(kind, param):
    return (
        make_pipeline(StandardScaler(), Ridge(alpha=param))
        if kind == "ridge"
        else HistGradientBoostingRegressor(
            max_leaf_nodes=param,
            max_iter=50,
            learning_rate=0.05,
            random_state=1729,
            early_stopping=False,
        )
    )


def predict(d, out):
    d = d.dropna(subset=FEATURES + ["entry_ts"])
    rows = []
    logs = []
    attempts = []
    coeff = []
    for start, train, test in folds(d):
        a, b, cutoff = inner(train)
        fid = start.strftime("%Y-%m")
        base = test[
            [
                "session",
                "symbol",
                "signal_ts",
                "entry_ts",
                "label_end",
                "target",
                "volatility",
                "ret20",
            ]
        ].copy()
        base["fold"] = fid
        base["model"] = "momentum"
        base["prediction"] = test.ret20 / 20
        rows.append(base.copy())
        for kind, grid in [("ridge", [1.0, 100.0]), ("boost", [15, 31])]:
            scores = []
            for param in grid:
                m = estimator(kind, param)
                m.fit(a[FEATURES], a.target)
                score = mean_squared_error(b.target, m.predict(b[FEATURES]))
                scores.append((score, param))
                attempts.append(
                    dict(fold=fid, model=kind, param=param, inner_mse=score, status="ok")
                )
            _, param = min(scores)
            m = estimator(kind, param)
            m.fit(train[FEATURES], train.target)
            with open(out / f"{kind}-{fid}.pkl", "wb") as f:
                pickle.dump(m, f)
            base["model"] = kind
            base["prediction"] = m.predict(test[FEATURES])
            rows.append(base.copy())
            if kind == "ridge":
                for feature, value in zip(FEATURES, m[-1].coef_ / m[0].scale_):
                    coeff.append(dict(fold=fid, feature=feature, coefficient_raw_units=value))
        logs.append(
            dict(
                fold=fid,
                train_start=str(train.signal_ts.min()),
                train_end=str(train.signal_ts.max()),
                latest_information=str(train.label_end.max()),
                fit_cutoff=str(start),
                inner_cutoff=str(cutoff),
                inner_train=len(a),
                inner_validation=len(b),
                purged_inner=int(((train.signal_ts < cutoff) & (train.label_end >= cutoff)).sum()),
                train_rows=len(train),
                test_rows=len(test),
                test_start=str(test.signal_ts.min()),
                test_end=str(test.signal_ts.max()),
            )
        )
    p = pd.concat(rows, ignore_index=True)
    assert not p.duplicated(["model", "symbol", "signal_ts"]).any()
    pd.DataFrame(logs).to_csv(out / "folds.csv", index=False)
    pd.DataFrame(attempts).to_csv(out / "experiments.csv", index=False)
    pd.DataFrame(coeff).to_csv(out / "ridge_coefficients.csv", index=False)
    return p
