"""Unit tests for core/filters.py — vector field outlier filters."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.filters import (
    filter_global,
    filter_median,
    filter_vecstd,
    func_hist_filter,
    _local_stats_nan,
)


# ---------------------------------------------------------------------------
# filter_median
# ---------------------------------------------------------------------------

class TestFilterMedian:
    def test_detects_obvious_outlier(self):
        u = np.ones((8, 8))
        u[4, 4] = 100.0
        result, changed = filter_median(u, vec_std=2.5)
        assert changed is True
        assert np.isnan(result[4, 4])

    def test_uniform_field_unchanged(self):
        u = np.ones((8, 8)) * 5.0
        result, changed = filter_median(u, vec_std=2.5)
        assert changed is False
        np.testing.assert_array_equal(result, u)

    def test_preserves_shape(self):
        u = np.random.randn(12, 16)
        result, _ = filter_median(u)
        assert result.shape == u.shape

    def test_all_nan_input(self):
        u = np.full((4, 4), np.nan)
        result, changed = filter_median(u)
        assert changed is False
        assert np.all(np.isnan(result))

    def test_single_element(self):
        u = np.array([[5.0]])
        result, changed = filter_median(u)
        assert changed is False

    def test_does_not_modify_input(self):
        u = np.ones((6, 6))
        u[3, 3] = 50.0
        u_orig = u.copy()
        filter_median(u)
        np.testing.assert_array_equal(u, u_orig)


# ---------------------------------------------------------------------------
# filter_vecstd
# ---------------------------------------------------------------------------

class TestFilterVecstd:
    def test_detects_extreme_outlier(self):
        np.random.seed(1)
        u = np.random.randn(10, 10)
        u[5, 5] = 50.0
        result, changed = filter_vecstd(u, vec_std=2.0)
        assert changed is True
        assert np.isnan(result[5, 5])

    def test_mild_variation_unchanged(self):
        np.random.seed(0)
        u = np.random.randn(8, 8) * 0.1
        result, changed = filter_vecstd(u, vec_std=3.0)
        assert changed is False

    def test_all_zeros(self):
        u = np.zeros((4, 4))
        result, changed = filter_vecstd(u)
        assert changed is False


# ---------------------------------------------------------------------------
# filter_global
# ---------------------------------------------------------------------------

class TestFilterGlobal:
    def test_detects_global_outlier(self):
        u = np.zeros((8, 8))
        v = np.zeros((8, 8))
        u[3, 3] = 100.0
        v[3, 3] = -100.0
        uo, vo = filter_global(u, v, r_mm=3.0)
        assert np.isnan(uo[3, 3])
        assert np.isnan(vo[3, 3])

    def test_uniform_field_unchanged(self):
        u = np.ones((6, 6)) * 2.0
        v = np.ones((6, 6)) * 3.0
        uo, vo = filter_global(u, v)
        assert not np.any(np.isnan(uo))
        assert not np.any(np.isnan(vo))

    def test_all_nan_returns_early(self):
        u = np.full((4, 4), np.nan)
        v = np.full((4, 4), np.nan)
        uo, vo = filter_global(u, v)
        assert np.all(np.isnan(uo))
        assert np.all(np.isnan(vo))

    def test_does_not_modify_input(self):
        u = np.ones((6, 6))
        v = np.ones((6, 6))
        u[0, 0] = 999.0
        u_orig = u.copy()
        filter_global(u, v)
        np.testing.assert_array_equal(u, u_orig)

    def test_preserves_shape(self):
        u = np.random.randn(10, 14)
        v = np.random.randn(10, 14)
        uo, vo = filter_global(u, v)
        assert uo.shape == u.shape
        assert vo.shape == v.shape


# ---------------------------------------------------------------------------
# func_hist_filter
# ---------------------------------------------------------------------------

class TestFuncHistFilter:
    def test_basic_statistics(self):
        u = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        mean, std, median = func_hist_filter(u, std_limit=3.0)
        assert abs(mean - 3.0) < 1e-10
        assert abs(median - 3.0) < 1e-10

    def test_empty_valid_data(self):
        u = np.full(5, np.nan)
        mean, std, median = func_hist_filter(u)
        assert np.isnan(mean) and np.isnan(std) and np.isnan(median)

    def test_outlier_excluded(self):
        u = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 100.0])
        mean, std, median = func_hist_filter(u, std_limit=1.0)
        assert mean < 10.0


# ---------------------------------------------------------------------------
# _local_stats_nan helper
# ---------------------------------------------------------------------------

class TestLocalStatsNan:
    def test_returns_three_arrays(self):
        u = np.random.randn(8, 8)
        mean_m, std_m, med_m = _local_stats_nan(u, 3, compute_median=True)
        assert mean_m.shape == u.shape
        assert std_m.shape == u.shape
        assert med_m.shape == u.shape

    def test_skip_median(self):
        u = np.random.randn(6, 6)
        mean_m, std_m, med_m = _local_stats_nan(u, 3, compute_median=False)
        assert med_m is None
        assert mean_m.shape == u.shape
