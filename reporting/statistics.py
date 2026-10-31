"""Diagnostics with explicit handling of undefined correlations."""

import numpy as np
import pandas as pd


def rank_correlation(left, right):
    """Pairwise-finite Spearman correlation; undefined samples return NaN.

    Align Series by index and rank only jointly observed pairs. Constant
    samples contain no ranking information and must not be reported as zero.
    """
    pairs = pd.concat([pd.Series(left), pd.Series(right)], axis=1)
    pairs = pairs.replace([np.inf, -np.inf], np.nan).dropna()
    if len(pairs) < 2 or (pairs.nunique() < 2).any():
        return float("nan")
    ranks = pairs.rank(method="average")
    return float(ranks.iloc[:, 0].corr(ranks.iloc[:, 1]))
