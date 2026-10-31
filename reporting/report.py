import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from reporting.statistics import rank_correlation


def metrics(e, initial=100000):
    r = e.equity.pct_change()
    r.iloc[0] = e.equity.iloc[0] / initial - 1
    wealth = np.r_[initial, e.equity]
    dd = wealth / np.maximum.accumulate(wealth) - 1
    duration = longest = 0
    for x in dd:
        duration = duration + 1 if x < -1e-12 else 0
        longest = max(longest, duration)
    vol = r.std() * np.sqrt(252)
    total = e.equity.iloc[-1] / initial - 1
    return dict(
        start=e.session.iloc[0],
        end=e.session.iloc[-1],
        sessions=len(e),
        total_return=total,
        annual_return=(1 + total) ** (252 / len(e)) - 1,
        volatility=vol,
        sharpe=r.mean() * 252 / vol if vol > 1e-12 else np.nan,
        max_drawdown=dd.min(),
        drawdown_duration=longest,
        turnover=e.turnover.sum(),
        exposure=e.exposure.mean(),
        costs=(e.fees + e.slippage).sum(),
        max_reconciliation=e.residual.abs().max(),
    )


def bootstrap(e, seed=1729):
    r = e.equity.pct_change().dropna().to_numpy()
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(200):
        starts = rng.integers(0, len(r), int(np.ceil(len(r) / 20)))
        sample = np.concatenate([r[(s + np.arange(20)) % len(r)] for s in starts])[: len(r)]
        vals.append(np.prod(1 + sample) ** (252 / len(sample)) - 1)
    return np.quantile(vals, [0.025, 0.975])


def generate(out):
    out = Path(out)
    manifest = json.loads((out / "manifest.json").read_text())
    p = pd.read_parquet(out / "predictions.parquet")
    rows = []
    segments = []
    unc = []
    fig, axes = plt.subplots(3, 2, figsize=(14, 12))
    curves = {}
    for model in ["momentum", "ridge", "boost", "buyhold", "cash"]:
        e = pd.read_csv(out / f"{model}-base-equity.csv")
        g = pd.read_csv(out / f"{model}-gross-equity.csv")
        curves[model] = e
        m = metrics(e)
        m.update(
            model=model,
            gross_return=metrics(g)["total_return"],
            cost_drag=metrics(g)["total_return"] - m["total_return"],
            trade_count=len(pd.read_csv(out / f"{model}-base-fills.csv")),
        )
        rows.append(m)
        bounds = [
            ("development", "2013-01-01", "2023-12-31"),
            ("final", "2024-01-01", "2025-12-31"),
        ] + [(str(y), f"{y}-01-01", f"{y}-12-31") for y in range(2013, 2026)]
        bounds += [
            (f"{y}-{mo:02}", f"{y}-{mo:02}-01", f"{y}-06-30" if mo == 1 else f"{y}-12-31")
            for y in range(2013, 2026)
            for mo in [1, 7]
        ]
        for label, start, end in bounds:
            ix = e.index[e.session.between(start, end)]
            if len(ix):
                net_metrics = metrics(
                    e.loc[ix].reset_index(drop=True),
                    100000 if ix[0] == 0 else e.equity.iloc[ix[0] - 1],
                )
                gross_metrics = metrics(
                    g.loc[ix].reset_index(drop=True),
                    100000 if ix[0] == 0 else g.equity.iloc[ix[0] - 1],
                )
                segments.append(
                    dict(
                        model=model,
                        period=label,
                        **net_metrics,
                        gross_return=gross_metrics["total_return"],
                        gross_annual_return=gross_metrics["annual_return"],
                    )
                )
        lo, hi = bootstrap(e)
        unc.append(dict(model=model, annual_return_low=lo, annual_return_high=hi))
        axes[0, 0].plot(pd.to_datetime(e.session), e.equity / 100000, label=model + " net")
        axes[0, 0].plot(pd.to_datetime(g.session), g.equity / 100000, alpha=0.25, linestyle="--")
        axes[0, 1].plot(pd.to_datetime(e.session), e.equity / e.equity.cummax() - 1, label=model)
        axes[1, 0].plot(
            pd.to_datetime(e.session), e.equity.pct_change().rolling(252).mean() * 252, label=model
        )
        axes[1, 1].plot(pd.to_datetime(e.session), e.turnover.rolling(63).sum(), label=model)
        axes[2, 0].plot(pd.to_datetime(e.session), (e.fees + e.slippage).cumsum(), label=model)
    summary = pd.DataFrame(rows)
    summary.to_csv(out / "summary.csv", index=False)
    pd.DataFrame(segments).to_csv(out / "periods.csv", index=False)
    pd.DataFrame(unc).to_csv(out / "uncertainty.csv", index=False)
    years = pd.DataFrame(segments)
    years = years[years.period.str.fullmatch(r"\d{4}")]
    years.pivot(index="period", columns="model", values="total_return").plot.bar(ax=axes[2, 1])
    for ax, title in zip(
        axes.flat,
        [
            "Equity: net solid, gross dashed",
            "Net drawdown",
            "Rolling 252-session mean return ×252",
            "63-session traded notional / prior equity",
            "Cumulative explicit costs ($)",
            "Net calendar-year returns",
        ],
    ):
        ax.set_title(title)
        ax.legend(fontsize=7)
        ax.xaxis.set_major_locator(plt.MaxNLocator(6))
        ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(out / "performance.png")
    plt.close(fig)
    quality = []
    for model, group in p.dropna(subset=["target"]).groupby("model"):
        for label, g in [
            ("development", group[group.session < "2024-01-01"]),
            ("final", group[group.session >= "2024-01-01"]),
        ]:
            ic = g.groupby("session").apply(
                lambda x: rank_correlation(x.prediction, x.target), include_groups=False
            )
            quality.append(
                dict(
                    model=model,
                    period=label,
                    n=len(g),
                    mse=((g.prediction - g.target) ** 2).mean(),
                    zero_mse=(g.target**2).mean(),
                    mean_cross_sectional_rank_ic=ic.mean(),
                    ic_std=ic.std(),
                    ic_sessions_total=len(ic),
                    ic_sessions_valid=int(ic.notna().sum()),
                    ic_sessions_undefined=int(ic.isna().sum()),
                )
            )
    pd.DataFrame(quality).to_csv(out / "predictive_quality.csv", index=False)
    stress = []
    for path in sorted(out.glob("*-equity.csv")):
        name = path.name[:-11]
        if any(name.endswith("-" + x) for x in ["half", "double", "delay"]):
            stress.append(dict(scenario=name, **metrics(pd.read_csv(path))))
    pd.DataFrame(stress).to_csv(out / "stress.csv", index=False)
    diagnostic = pd.read_csv(out / "diagnostics.csv")
    fig, axes = plt.subplots(1, 2, figsize=(13, 4))
    diagnostic.assign(label=diagnostic.model + ":" + diagnostic.variant).set_index(
        "label"
    ).mse.plot.bar(ax=axes[0])
    axes[0].set_title("Development diagnostics: held-out MSE")
    pd.read_csv(out / "ridge_coefficients.csv").groupby(
        "feature"
    ).coefficient_raw_units.mean().plot.bar(ax=axes[1])
    axes[1].set_title("Ridge mean raw-unit coefficients")
    fig.tight_layout()
    fig.savefig(out / "diagnostics.png")
    plt.close(fig)
    fills = pd.read_csv(out / "ridge-base-fills.csv")
    first = fills[fills.filled != 0].iloc[0]
    trace = (
        p[
            (p.model == "ridge")
            & (p.symbol == first.symbol)
            & (p.signal_ts == pd.Timestamp(first.signal_ts))
        ]
        .iloc[0]
        .to_dict()
    )
    trace.update(first.to_dict())
    trace["account"] = (
        curves["ridge"].loc[curves["ridge"].session == first.session].iloc[0].to_dict()
    )
    (out / "trade_trace.json").write_text(json.dumps(trace, default=str, indent=2))
    label = (
        "SYNTHETIC ENGINEERING VALIDATION — NOT MARKET PERFORMANCE"
        if manifest["synthetic"]
        else "HISTORICAL NORMALIZED-PRICE EXPERIMENT"
    )
    table = summary[
        ["model", "total_return", "gross_return", "max_drawdown", "turnover", "exposure"]
    ].to_markdown(index=False, floatfmt=".4f")
    interpretation = " ".join(
        f"{r.model}: net return {r.total_return:.1%}, gross return {r.gross_return:.1%}, average exposure {r.exposure:.1%}, and two-sided turnover {r.turnover:.1f}×."
        for r in summary.itertuples()
        if r.model in ["momentum", "ridge", "boost"]
    )
    text = f"""# Market Signal Lab\n\n**{label}**\n\nDecision: refine data and external validation; alpha is not established. Results are calculated from saved C++ execution artifacts.\n\n## Question and protocol\nDo trailing daily price/liquidity features predict next-open to subsequent-open returns strongly enough to survive costs? Momentum hypothesizes persistence; Ridge additive relationships; boosting nonlinear interactions. See ../../docs/protocol.md and contracts.md. Universe is fixed across eight surviving ETFs, introducing retrospective selection bias.\n\n{table}\n\nEvaluation is continuous from 2013 through 2025; periods.csv contains exact segment dates and counts, including the 2024–2025 retrospective holdout. Synthetic dates do not imply historical observations.\n\n![Saved performance plots](performance.png)\n\n![Development diagnostics](diagnostics.png)\n\nThe first Ridge trade is traced in trade_trace.json from close-generated signal and forecast to eligible open, rounded shares, costs, cash and closing equity.\n\n## Accounting and metrics\n$100,000 initial capital; 1bp commission + 5bp adverse slippage per traded open notional; integer normalized shares, long only. Cash yields zero; gross is an independent zero-cost replay. Returns are close-to-close including initial trade costs. Annualization uses 252 sessions; Sharpe is mean daily return / sample standard deviation ×sqrt(252), zero risk-free rate. Undefined zero-volatility Sharpe is blank. Drawdown includes initial capital; duration counts sessions below the high-water mark. Turnover sums absolute traded reference notional / prior close equity (two-sided). Final holdings are marked, not liquidated. Buy-and-hold purchases equal weights once and has drifting exposures; active strategies carry cash and are not exposure-matched.\n\nMax absolute accounting residual: {summary.max_reconciliation.max():.3g} dollars. Per-symbol attribution and positions reconcile to portfolio equity; costs are subtracted once. Stale marks and rejected orders are explicit.\n\n## Evidence and limitations\n{interpretation} These observed synthetic-account differences show how turnover and costs affect the implemented strategies; they do not explain real market behavior or establish alpha.\n\nPredictive quality (MSE against zero; daily cross-sectional rank correlation) is in predictive_quality.csv. Eight symbols make daily IC unstable. Correlation is undefined for constant or insufficient paired observations; these sessions are excluded from IC averages and their counts are reported explicitly, not treated as zero. Ridge raw-unit coefficients, training-only complexity comparisons, development ablations and permutation diagnostics are saved separately. They describe associations, not causal drivers. Transaction costs and changing exposure can overwhelm small predictive differences. Stress cases in stress.csv use half/double costs and an additional session delay, with identical frozen policy. No final results are used for selection.\n\nSignal decay uses OOS signals only, with horizons 1/2/5/10 measured from executable open; overlapping observations and common market exposure invalidate IID significance. uncertainty.csv uses 200 circular moving-block bootstrap draws of 20-session portfolio returns. This is descriptive uncertainty, does not resolve multiple experimentation or regime change, and synthetic intervals say nothing about markets.\n\n## Execution and replay\nSynthetic intraday experiments use identical parent orders and a fixed prior-session volume profile. Fills occur at completed bar end with 10% participation; residuals carry within the day and cancel at its end. TWAP/VWAP change the holding horizon and are not market evidence. paper.sqlite is transactional historical replay, not a prospective live track record.\n\n## Audit and next experiment\nTests cover future perturbation, fold purity, timing, independent Python/C++ accounting, costs, malformed contracts, cash limits, and replay idempotence. See verification.txt. Training boundaries and every attempted hyperparameter are in folds.csv and experiments.csv. Input, source, configuration and model hashes are in manifest.json.\n\nThe next justified experiment is to import independently documented consistent-adjustment data, verify inception/coverage and corporate actions, then rerun this frozen protocol. Real market returns, execution quality, and profitable alpha remain unmeasured when data is synthetic. The manual daily command imports completed sessions, rejects stale data, fits matured labels, and persists pending signals. Its provider retrieval is operator-driven; no prospective market observations have been accumulated.\n"""
    if not manifest["synthetic"]:
        text = text.replace(
            "Synthetic dates do not imply historical observations.",
            "Prices are real Yahoo Finance historical observations, normalized using the current adjustment vintage; see ../../docs/yahoo-data.md and store/metadata.json for provenance.",
        )
        text = text.replace(
            "These observed synthetic-account differences show how turnover and costs affect the implemented strategies; they do not explain real market behavior or establish alpha.",
            "These historical simulation differences show the effects of exposure, turnover and costs under the frozen policy; they do not establish risk-adjusted alpha or actual executable profits.",
        )
        text = text.replace(
            "and synthetic intervals say nothing about markets.",
            "and these intervals do not account for provider revisions or retrospective universe selection.",
        )
        text = text.replace(
            "The next justified experiment is to import independently documented consistent-adjustment data, verify inception/coverage and corporate actions, then rerun this frozen protocol. Real market returns, execution quality, and profitable alpha remain unmeasured when data is synthetic.",
            "The next justified experiment is independent-provider validation and point-in-time corporate-action accounting. Current-vintage adjusted prices can contain later revisions; absolute liquidity features and normalized share rounding can depend on future adjustments. This is a preliminary historical normalized-price experiment, not a point-in-time or live track record. Alpha and actual execution quality remain unestablished.",
        )
        text = text.replace(
            "Its provider retrieval is operator-driven;",
            "Yahoo retrieval is available through research.download_yahoo;",
        )
    (out / "report.md").write_text(text)
