"""Testes unitários para src/utils/eda.py."""

import numpy as np
import pandas as pd
import pytest

from src.utils.eda import (
    compute_descriptive_stats,
    compute_null_profile,
    detect_outliers_iqr,
    min_max_normalize,
    winsorize_series,
)


def test_compute_null_profile():
    df = pd.DataFrame({"a": [1, 2, np.nan], "b": [np.nan, np.nan, np.nan], "c": [1, 2, 3]})
    profile = compute_null_profile(df)

    assert profile.shape[0] == 3
    assert profile.loc[profile["coluna"] == "b", "pct_nulos"].values[0] == 100.0
    assert profile.loc[profile["coluna"] == "c", "pct_nulos"].values[0] == 0.0
    # Deve estar ordenado por pct_nulos decrescente
    assert profile.iloc[0]["coluna"] == "b"


def test_compute_descriptive_stats():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5], "y": [10, 20, 30, 40, 50]})
    stats = compute_descriptive_stats(df)

    assert "skewness" in stats.columns
    assert "kurtosis" in stats.columns
    assert "iqr" in stats.columns
    assert "missing_pct" in stats.columns
    assert stats.loc["x", "mean"] == 3.0


def test_winsorize_series():
    s = pd.Series([1, 2, 3, 100, 200])
    w = winsorize_series(s, lower=0.0, upper=0.8)

    upper_limit = s.quantile(0.8)
    assert w.max() <= upper_limit
    assert w.min() == 1.0


def test_min_max_normalize():
    s = pd.Series([0, 5, 10])
    n = min_max_normalize(s)

    assert n.min() == pytest.approx(0.0)
    assert n.max() == pytest.approx(1.0)
    assert n.iloc[1] == pytest.approx(0.5)


def test_min_max_normalize_constant():
    s = pd.Series([5, 5, 5])
    n = min_max_normalize(s)

    assert (n == 0.0).all()


def test_detect_outliers_iqr():
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5, 100]})
    outliers = detect_outliers_iqr(df, "x")

    assert outliers.shape[0] == 1
    assert outliers["x"].values[0] == 100
