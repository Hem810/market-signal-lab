import warnings
import numpy as np
import pandas as pd
import pytest
from reporting.statistics import rank_correlation


@pytest.mark.parametrize(
    "left,right",
    [
        ([1, 1, 1], [1, 2, 3]),
        ([1, 2, 3], [4, 4, 4]),
        ([], []),
        ([1], [2]),
        ([1, np.nan], [np.nan, 2]),
    ],
)
def test_undefined_rank_correlation_is_nan_without_warning(left, right):
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        assert np.isnan(rank_correlation(left, right))


@pytest.mark.parametrize(
    "left,right,expected",
    [
        ([1, 2, 3], [3, 2, 1], -1),
        ([1, 1, 2], [2, 2, 4], 1),
        ([1, np.inf, 3, np.nan], [2, 7, 6, 8], 1),
    ],
)
def test_rank_correlation_valid_pairs_and_ties(left, right, expected):
    assert rank_correlation(left, right) == pytest.approx(expected)


def test_rank_correlation_aligns_indices_before_ranking():
    left = pd.Series([1, 2, 3], index=["a", "b", "c"])
    right = pd.Series([1, 2, 3], index=["c", "b", "a"])
    assert rank_correlation(left, right) == pytest.approx(-1)
