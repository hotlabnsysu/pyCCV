"""Vorticity computation methods for the pyCCV VIEWER.

Three implementations:
  CDM  — Central Difference Method (np.gradient)
  CM   — Circulation Method (Stokes' theorem via convolution)
  LSD  — Least Squares Differentiation
"""

from __future__ import annotations

import numpy as np
from scipy.signal import convolve2d


# Map display name → internal code
METHOD_MAP = {
    "Central Difference":          "CDM",
    "Stokes' Theorem":             "CM",
    "Least Squares Differentiation": "LSD",
}


def _get_grid_spacing(x: np.ndarray, y: np.ndarray):
    """Return (dx, dy) from 2-D coordinate arrays. Safe for non-uniform grids."""
    if x.ndim == 2 and x.shape[1] > 1:
        dx = float(np.median(np.diff(x[0, :])))
    elif x.ndim == 1 and len(x) > 1:
        dx = float(np.median(np.diff(x)))
    else:
        dx = 1.0

    if y.ndim == 2 and y.shape[0] > 1:
        dy = float(np.median(np.diff(y[:, 0])))
    elif y.ndim == 1 and len(y) > 1:
        dy = float(np.median(np.diff(y)))
    else:
        dy = 1.0

    if dx == 0:
        dx = 1.0
    if dy == 0:
        dy = 1.0
    return dx, dy


def calculate_vorticity_cdm(
    x: np.ndarray, y: np.ndarray, u: np.ndarray, v: np.ndarray
) -> np.ndarray:
    """Central Difference Method.

    ω = ∂v/∂x − ∂u/∂y   (negated vs. CM/LSD — preserved from original Viewer code)
    """
    dx, dy = _get_grid_spacing(x, y)
    dudy = np.gradient(u, dy, axis=0)
    dvdx = np.gradient(v, dx, axis=1)
    return -(dvdx - dudy)


def calculate_vorticity_cm(
    x: np.ndarray, y: np.ndarray, u: np.ndarray, v: np.ndarray
) -> np.ndarray:
    """Circulation Method (Stokes' theorem via 3×3 Sobel-like kernels)."""
    dx, dy = _get_grid_spacing(x, y)

    # Sobel-style kernels for circulation
    kernel_x = np.array([
        [-1, 0, 1],
        [-2, 0, 2],
        [-1, 0, 1],
    ], dtype=float) / (8.0 * dx)

    kernel_y = np.array([
        [-1, -2, -1],
        [ 0,  0,  0],
        [ 1,  2,  1],
    ], dtype=float) / (8.0 * dy)

    dvdx = convolve2d(v, kernel_x, mode="same", boundary="symm")
    dudy = convolve2d(u, kernel_y, mode="same", boundary="symm")
    return dvdx - dudy


def calculate_vorticity_lsd(
    x: np.ndarray, y: np.ndarray, u: np.ndarray, v: np.ndarray
) -> np.ndarray:
    """Least Squares Differentiation via 3×3 kernels."""
    dx, dy = _get_grid_spacing(x, y)

    kernel_x = np.array([
        [-1, 0, 1],
        [-1, 0, 1],
        [-1, 0, 1],
    ], dtype=float) / (6.0 * dx)

    kernel_y = np.array([
        [-1, -1, -1],
        [ 0,  0,  0],
        [ 1,  1,  1],
    ], dtype=float) / (6.0 * dy)

    dvdx = convolve2d(v, kernel_x, mode="same", boundary="symm")
    dudy = convolve2d(u, kernel_y, mode="same", boundary="symm")
    return dvdx - dudy


def compute_vorticity(
    x: np.ndarray,
    y: np.ndarray,
    u: np.ndarray,
    v: np.ndarray,
    method: str = "CDM",
) -> np.ndarray:
    """Compute vorticity with automatic 1-D → 2-D reshape.

    Parameters
    ----------
    method : "CDM" | "CM" | "LSD"  (internal codes; use METHOD_MAP to convert from display names)
    """
    # Reshape flat arrays to 2-D if needed
    if u.ndim == 1:
        n = u.size
        ny = int(np.round(np.sqrt(n)))
        nx = n // ny
        u = u.reshape(ny, nx)
        v = v.reshape(ny, nx)
        if x.ndim == 1:
            x = x.reshape(ny, nx)
        if y.ndim == 1:
            y = y.reshape(ny, nx)

    if method == "CDM":
        return calculate_vorticity_cdm(x, y, u, v)
    elif method == "CM":
        return calculate_vorticity_cm(x, y, u, v)
    elif method == "LSD":
        return calculate_vorticity_lsd(x, y, u, v)
    else:
        return calculate_vorticity_cdm(x, y, u, v)
