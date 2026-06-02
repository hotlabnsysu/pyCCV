"""Unit tests for sub-pixel peak refinement in core/piv_fft.py."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.piv_fft import _batch_subpix_gauss, _batch_subpix_2d_gauss


def _make_gaussian_peak(cx, cy, size=15, sigma=2.0):
    """Create a 2D Gaussian correlation map with peak at (cx, cy)."""
    y, x = np.mgrid[0:size, 0:size]
    g = np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))
    return g


class TestBatchSubpixGauss:
    def test_integer_peak_exact(self):
        corr = _make_gaussian_peak(7.0, 7.0, size=15)
        stack = corr[np.newaxis]
        sub_x, sub_y = _batch_subpix_gauss(stack, np.array([7]), np.array([7]))
        assert abs(sub_x[0] - 7.0) < 0.01
        assert abs(sub_y[0] - 7.0) < 0.01

    def test_subpixel_offset(self):
        corr = _make_gaussian_peak(7.3, 7.6, size=15)
        peak_x, peak_y = 7, 8
        stack = corr[np.newaxis]
        sub_x, sub_y = _batch_subpix_gauss(stack, np.array([peak_x]), np.array([peak_y]))
        assert abs(sub_x[0] - 7.3) < 0.15
        assert abs(sub_y[0] - 7.6) < 0.15

    def test_zero_displacement(self):
        corr = _make_gaussian_peak(7.0, 7.0, size=15)
        stack = corr[np.newaxis]
        sub_x, sub_y = _batch_subpix_gauss(stack, np.array([7]), np.array([7]))
        assert abs(sub_x[0] - 7.0) < 0.01
        assert abs(sub_y[0] - 7.0) < 0.01

    def test_batch_multiple(self):
        peaks = [(7.2, 7.4), (6.8, 7.1)]
        stack = np.stack([_make_gaussian_peak(cx, cy, size=15) for cx, cy in peaks])
        px = np.array([7, 7])
        py = np.array([7, 7])
        sub_x, sub_y = _batch_subpix_gauss(stack, px, py)
        assert sub_x.shape == (2,)
        assert sub_y.shape == (2,)


class TestBatchSubpix2dGauss:
    def test_integer_peak_exact(self):
        corr = _make_gaussian_peak(7.0, 7.0, size=15)
        stack = corr[np.newaxis]
        sub_x, sub_y = _batch_subpix_2d_gauss(stack, np.array([7]), np.array([7]))
        assert abs(sub_x[0] - 7.0) < 0.01
        assert abs(sub_y[0] - 7.0) < 0.01

    def test_subpixel_offset(self):
        corr = _make_gaussian_peak(7.3, 7.6, size=15)
        peak_x, peak_y = 7, 8
        stack = corr[np.newaxis]
        sub_x, sub_y = _batch_subpix_2d_gauss(stack, np.array([peak_x]), np.array([peak_y]))
        assert abs(sub_x[0] - 7.3) < 0.15
        assert abs(sub_y[0] - 7.6) < 0.15

    def test_flat_peak_fallback(self):
        """When correlation surface is flat, delta should be ~0 (no crash)."""
        corr = np.ones((15, 15))
        stack = corr[np.newaxis]
        sub_x, sub_y = _batch_subpix_2d_gauss(stack, np.array([7]), np.array([7]))
        assert abs(sub_x[0] - 7.0) < 0.5
        assert abs(sub_y[0] - 7.0) < 0.5

    def test_large_displacement(self):
        corr = _make_gaussian_peak(3.0, 11.0, size=15)
        stack = corr[np.newaxis]
        sub_x, sub_y = _batch_subpix_2d_gauss(stack, np.array([3]), np.array([11]))
        assert abs(sub_x[0] - 3.0) < 0.01
        assert abs(sub_y[0] - 11.0) < 0.01

    def test_batch_multiple(self):
        peaks = [(5.3, 9.7), (10.1, 4.4), (7.0, 7.0)]
        stack = np.stack([_make_gaussian_peak(cx, cy, size=15) for cx, cy in peaks])
        px = np.array([5, 10, 7])
        py = np.array([10, 4, 7])
        sub_x, sub_y = _batch_subpix_2d_gauss(stack, px, py)
        assert sub_x.shape == (3,)
        assert sub_y.shape == (3,)
