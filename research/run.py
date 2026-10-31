import argparse, hashlib, json, os, platform, subprocess, time
from pathlib import Path
import importlib.metadata
import numpy as np
import pandas as pd
import yaml
from research.store import synthetic, ingest, digest, calendar
from research.features import engineer, FEATURES
from research.models import predict, estimator
from research.portfolio import weights
from research.export import signals, market
from research.execution import execute
from paper.loop import replay
from reporting.report import generate
from reporting.statistics import rank_correlation


def run(config, raw=None, provider=None, documentation=None, run_id="demo"):
    started = time.time()
    cfg = yaml.safe_load(Path(config).read_text())
    out = Path("artifacts") / run_id
    if (cfg["start"], cfg["end"], cfg["final_start"], cfg["seed"]) != (
        "2010-01-01",
        "2025-12-31",
        "2024-01-01",
        1729,
    ):
        raise ValueError(
            "Date boundaries/seed are frozen; edit the protocol and harness explicitly for a new study"
        )
    if out.exists():
        raise ValueError("Run directory exists; choose a new --run-id to preserve artifacts")
    out.mkdir(parents=True)
    (out / "protocol.md").write_bytes(Path("docs/protocol.md").read_bytes())
    (out / "config.yaml").write_bytes(Path(config).read_bytes())
    if raw is None:
        raw = "data/raw/synthetic"
        synthetic(raw, seed=cfg["seed"])
        provider = "synthetic"
    d = ingest(raw, out / "store", provider, documentation)
    if set(d.symbol) != set(cfg["symbols"]):
        raise ValueError("Universe differs from frozen config")
    f = engineer(d)
    p = predict(f, out)
    p = pd.concat([weights(g) for _, g in p.groupby(["model", "signal_ts"])], ignore_index=True)
    p.to_parquet(out / "predictions.parquet", index=False)
    market(d[d.session <= pd.Timestamp(cfg["end"])], out / "market.csv")
    for model in ["momentum", "ridge", "boost", "buyhold", "cash"]:
        s = p[p.model == ("ridge" if model in ["buyhold", "cash"] else model)].copy()
        if model in ["buyhold", "cash"]:
            s = s[s.signal_ts == s.signal_ts.min()]
            s["model"] = model
            s["weight"] = 0.125 if model == "buyhold" else 0.0
        signals(s, out / f"{model}-signals.csv", run_id)
        for scenario, mult in [
            ("gross", 0),
            ("half", 0.5),
            ("base", 1),
            ("double", 2),
            ("delay", 1),
        ]:
            path = out / f"{model}-signals.csv"
            if scenario == "delay":
                delayed = s.copy()
                cal = calendar(
                    str(d.session.min().date()),
                    str((d.session.max() + pd.Timedelta(days=15)).date()),
                )
                mapping = dict(zip(cal.open, cal.open.shift(-1)))
                delayed["entry_ts"] = delayed.entry_ts.map(mapping)
                signals(delayed, out / f"{model}-delay-signals.csv", run_id)
                path = out / f"{model}-delay-signals.csv"
            command = [
                "build/market_sim",
                str(path),
                str(out / "market.csv"),
                str(out / f"{model}-{scenario}"),
                str(cfg["commission_bps"] * mult),
                str(cfg["slippage_bps"] * mult),
                str(cfg["initial_capital"]),
            ]
            subprocess.run(command, check=True)
    # OOS decay: no horizon selection; row-reindexing preserves missing exchange sessions.
    decay = []
    for h in [1, 2, 5, 10]:
        horizon = f[["session", "symbol"]].copy()
        horizon["forward"] = (
            f.groupby("symbol").open.shift(-(h + 1)) / f.groupby("symbol").open.shift(-1) - 1
        )
        q = p.merge(horizon, on=["session", "symbol"]).dropna(subset=["forward"])
        for (model, period), g in q.assign(
            period=np.where(q.session < "2024-01-01", "development", "final")
        ).groupby(["model", "period"]):
            decay.append(
                dict(
                    model=model,
                    period=period,
                    horizon=h,
                    n=len(g),
                    rank_correlation=rank_correlation(g.prediction, g.forward),
                )
            )
    pd.DataFrame(decay).to_csv(out / "decay.csv", index=False)
    # Development-only feature ablation / learning curve / permutation diagnostics.
    a = f[
        (f.label_end < pd.Timestamp("2022-01-01", tz="UTC"))
        & (f.session >= pd.Timestamp("2010-01-01"))
    ].dropna(subset=FEATURES + ["target"])
    b = f[
        (f.session >= pd.Timestamp("2022-01-01"))
        & (f.session < pd.Timestamp("2024-01-01"))
        & (f.label_end < pd.Timestamp("2024-01-01", tz="UTC"))
    ].dropna(subset=FEATURES + ["target"])
    diag = []
    for kind, param in [("ridge", 100), ("boost", 15)]:
        for variant, cols, train in [
            ("full", FEATURES, a),
            ("no_liquidity", [x for x in FEATURES if x != "liquidity"], a),
            ("recent_3y", FEATURES, a[a.session >= pd.Timestamp("2019-01-01")]),
        ]:
            m = estimator(kind, param)
            m.fit(train[cols], train.target)
            mse = np.mean((m.predict(b[cols]) - b.target) ** 2)
            diag.append(dict(model=kind, variant=variant, n_train=len(train), mse=mse))
            if variant == "full" and kind == "boost":
                rng = np.random.default_rng(1729)
                for col in cols:
                    shuffled = b[cols].copy()
                    shuffled[col] = rng.permutation(shuffled[col])
                    diag.append(
                        dict(
                            model=kind,
                            variant="permute_" + col,
                            n_train=len(train),
                            mse=np.mean((m.predict(shuffled) - b.target) ** 2),
                        )
                    )
    pd.DataFrame(diag).to_csv(out / "diagnostics.csv", index=False)
    pd.DataFrame(
        [
            execute(1000, k, [(100.0, 2000), (100.5, 4000), (99.8, 6000)])
            for k in ["immediate", "twap", "vwap"]
        ]
    ).to_json(out / "synthetic_execution.json", orient="records", indent=2)
    source = {
        str(x): digest(x)
        for folder in ["research", "paper", "reporting", "simulator", "configs", "docs"]
        for x in Path(folder).rglob("*")
        if x.is_file() and "__pycache__" not in str(x)
    }
    manifest = dict(
        run=run_id,
        synthetic=provider == "synthetic",
        created_at=pd.Timestamp.now(tz="UTC").isoformat(),
        runtime_seconds=time.time() - started,
        hardware=platform.platform(),
        processor=platform.machine(),
        python=platform.python_version(),
        versions={
            n: importlib.metadata.version(n)
            for n in [
                "numpy",
                "pandas",
                "scikit-learn",
                "matplotlib",
                "pyarrow",
                "exchange-calendars",
            ]
        },
        source_hashes=source,
        input_hash=digest(out / "store/market.parquet"),
        config_hash=digest(config),
        seed=1729,
        model_hashes={x.name: digest(x) for x in out.glob("*.pkl")},
        compiler=(
            subprocess.check_output(["clang++", "--version"], text=True)
            if platform.system() == "Darwin"
            else "see CMake build log"
        ),
    )
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "ledger_manifest.json").write_bytes((out / "manifest.json").read_bytes())
    runhash = digest(out / "ledger_manifest.json")
    s = pd.read_csv(out / "ridge-signals.csv")
    e = pd.read_csv(out / "ridge-base-equity.csv")
    fills = pd.read_csv(out / "ridge-base-fills.csv")
    try:
        replay(out / "paper.sqlite", s, e, fills, "2026-01-01T00:00:00Z", runhash, stop_after=11)
    except InterruptedError:
        pass
    n = replay(out / "paper.sqlite", s, e, fills, "2026-01-01T00:00:00Z", runhash)
    assert replay(out / "paper.sqlite", s, e, fills, "2026-01-01T00:00:00Z", runhash) == n
    (out / "replay_check.json").write_text(
        json.dumps(dict(unique_events=n, repeated_count=n, interrupted_after=11))
    )
    generate(out)
    manifest["runtime_seconds"] = time.time() - started
    manifest["artifact_hashes"] = {
        x.name: digest(x)
        for x in out.iterdir()
        if x.is_file() and x.suffix in [".csv", ".parquet", ".png"]
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(out / "report.md")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default="configs/base.yaml")
    p.add_argument("--raw")
    p.add_argument("--provider")
    p.add_argument("--documentation")
    p.add_argument("--run-id", default="demo")
    a = p.parse_args()
    run(a.config, a.raw, a.provider, a.documentation, a.run_id)
