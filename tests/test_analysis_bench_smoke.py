"""
Lightweight benchmark smoke tests.
These tests record elapsed time and peak memory for a small synthetic run.
They are NOT hard-gated performance assertions — they serve as comparative
baselines to detect regressions across refactoring phases.

Run with: pytest tests/test_analysis_bench_smoke.py -v -s
to see timing output.
"""
import sys
import os
import time

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.piv_fft import piv_fft_multi
from core.postprocess import post_process


def _make_synthetic_pair(size=128, particle_radius=2, num_particles=100, dx=4, dy=2, seed=0):
    """Create a synthetic image pair with known uniform displacement."""
    rng = np.random.default_rng(seed)
    img1 = np.zeros((size, size), dtype=np.uint8)
    xs = rng.integers(particle_radius, size - particle_radius, num_particles)
    ys = rng.integers(particle_radius, size - particle_radius, num_particles)
    for x, y in zip(xs, ys):
        img1[
            max(0, y - particle_radius): y + particle_radius + 1,
            max(0, x - particle_radius): x + particle_radius + 1,
        ] = 200
    img2 = np.zeros_like(img1)
    for x, y in zip(xs, ys):
        nx, ny = x + dx, y + dy
        if (particle_radius <= nx < size - particle_radius
                and particle_radius <= ny < size - particle_radius):
            img2[
                max(0, ny - particle_radius): ny + particle_radius + 1,
                max(0, nx - particle_radius): nx + particle_radius + 1,
            ] = 200
    return img1, img2


_POSTPROC_OPTS = {
    "enable_vel_limit": False,
    "u_min": -64, "u_max": 64, "v_min": -64, "v_max": 64,
    "thres_std": -1,
    "thres_median": -1,
    "thres_global": -1,
    "interp_method": -1,
    "smooth_data": False,
}


class TestCoreBenchSmoke:
    """Timing baseline for the PIV core on a small synthetic image pair."""

    def test_single_pair_piv_fft_completes_under_10s(self, capsys):
        img1, img2 = _make_synthetic_pair(size=128)

        t0 = time.perf_counter()
        x, y, u, v, s2n = piv_fft_multi(img1, img2, int_area_1=32, step=16, num_passes=1)
        elapsed = time.perf_counter() - t0

        with capsys.disabled():
            print(f"\n[bench] piv_fft_multi 128×128 pair: {elapsed:.3f}s")

        assert elapsed < 10.0, f"PIV FFT took {elapsed:.2f}s — unexpectedly slow"
        assert x is not None
        assert u.shape == v.shape

    def test_postprocess_completes_under_5s(self, capsys):
        img1, img2 = _make_synthetic_pair(size=128)
        x, y, u, v, s2n = piv_fft_multi(img1, img2, int_area_1=32, step=16, num_passes=1)

        t0 = time.perf_counter()
        results = post_process(u, v, _POSTPROC_OPTS)
        elapsed = time.perf_counter() - t0

        with capsys.disabled():
            print(f"\n[bench] post_process: {elapsed:.3f}s")

        assert elapsed < 5.0, f"post_process took {elapsed:.2f}s — unexpectedly slow"
        assert results is not None

    def test_full_pipeline_wall_time_baseline(self, capsys):
        """End-to-end baseline: PIV + postprocess for a small synthetic pair."""
        img1, img2 = _make_synthetic_pair(size=128)

        t0 = time.perf_counter()
        x, y, u, v, s2n = piv_fft_multi(img1, img2, int_area_1=32, step=16, num_passes=1)
        results = post_process(u, v, _POSTPROC_OPTS)
        elapsed = time.perf_counter() - t0

        with capsys.disabled():
            print(f"\n[bench] full pipeline 128×128: {elapsed:.3f}s")

        # Soft threshold only — this is a baseline marker, not a hard gate
        assert elapsed < 15.0, f"Full pipeline took {elapsed:.2f}s — investigate if this regresses"


class TestMemorySmoke:
    """Rough memory baseline using tracemalloc."""

    def test_single_pair_peak_memory_baseline(self, capsys):
        import tracemalloc

        img1, img2 = _make_synthetic_pair(size=256)

        tracemalloc.start()
        x, y, u, v, s2n = piv_fft_multi(img1, img2, int_area_1=32, step=16, num_passes=1)
        results = post_process(u, v, _POSTPROC_OPTS)
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        peak_mb = peak / 1024 / 1024
        with capsys.disabled():
            print(f"\n[bench] peak memory 256×256: {peak_mb:.1f} MB")

        # Soft guard — flag unexpectedly large allocations
        assert peak_mb < 500, f"Peak memory {peak_mb:.0f} MB is higher than expected"
