"""ViewerPresenter — stateless renderer for the VIEWER tab.

Draws vector / vorticity / image-only content onto a shared matplotlib Axes.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, Tuple

import numpy as np
import matplotlib.cm as mplcm
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


# Colormaps available in multi-colour vector mode and vorticity mode
COLORMAP_OPTIONS = ["plasma", "hsv", "rainbow", "jet", "turbo"]
_CMAP_ALIASES: Dict[str, str] = {"parula": "plasma"}


def _resolve_cmap(name: str) -> str:
    return _CMAP_ALIASES.get(name, name)


class ViewerPresenter:
    """Stateless presenter — call redraw() whenever viewer state changes."""

    def redraw(
        self,
        ax,
        fig,
        canvas,
        image: Optional[np.ndarray],
        vectors: Optional[Dict[str, np.ndarray]],
        grid_info: Optional[Dict],
        settings: Dict[str, Any],
    ) -> Tuple[bool, str, float, float]:
        """Render viewer content onto *ax*/*fig*/*canvas*.

        Parameters
        ----------
        image      : H×W or H×W×C uint8/float array, or None.
        vectors    : dict with keys 'x','y','u','v' as 2-D float arrays, or None.
        grid_info  : dict with 'dx','dy' (scalar spacing), or None.
        settings   : viewer settings dict (display_mode, colorbar_*, grid_skip, …).

        Returns
        -------
        (show_colorbar, cmap_name, vmin, vmax)
        """
        display_mode = settings.get("display_mode", "向量")
        _cb_info: Tuple[bool, str, float, float] = (False, "", 0.0, 1.0)

        # Preserve user zoom/pan across redraws
        try:
            prev_xlim = ax.get_xlim()
            prev_ylim = ax.get_ylim()
            has_prev_zoom = (prev_xlim != (0.0, 1.0) or prev_ylim != (0.0, 1.0))
        except Exception:
            has_prev_zoom = False

        fig.patch.set_facecolor("#2b2b2b")
        ax.clear()
        ax.set_facecolor("#1a1a1a")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

        if image is None and vectors is None:
            return _cb_info

        # ── Background image ─────────────────────────────────────────────
        if image is not None:
            if vectors is not None and grid_info is not None:
                x = vectors["x"]
                y = vectors["y"]
                dx = grid_info.get("dx", 1.0)
                dy = grid_info.get("dy", 1.0)
                extent = [
                    float(x.min()) - dx / 2,
                    float(x.max()) + dx / 2,
                    float(y.max()) + dy / 2,  # bottom (y-down convention)
                    float(y.min()) - dy / 2,  # top
                ]
                cmap_img = "gray" if image.ndim == 2 else None
                ax.imshow(image, extent=extent, aspect="equal", cmap=cmap_img, origin="upper")
            else:
                cmap_img = "gray" if image.ndim == 2 else None
                ax.imshow(image, cmap=cmap_img, origin="upper")

        # ── Vector / vorticity overlay ────────────────────────────────────
        if vectors is not None and display_mode in ("向量", "渦度"):
            x = vectors["x"]
            y = vectors["y"]
            u = vectors["u"]
            v = vectors["v"]

            skip = max(1, int(settings.get("grid_skip", 1)))
            xs = x[::skip, ::skip]
            ys = y[::skip, ::skip]
            us = u[::skip, ::skip]
            vs = v[::skip, ::skip]

            if display_mode == "向量":
                _cb_info = self._draw_vectors(ax, xs, ys, us, vs, settings)

            elif display_mode == "渦度":
                _cb_info = self._draw_vorticity(ax, x, y, u, v, xs, ys, settings)

        ax.set_axis_off()
        ax.set_aspect('equal', adjustable='box')
        fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        if has_prev_zoom:
            ax.set_xlim(prev_xlim)
            ax.set_ylim(prev_ylim)

        return _cb_info

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _draw_vectors(self, ax, xs, ys, us, vs, settings: Dict[str, Any]) -> Tuple[bool, str, float, float]:
        colorbar_enabled = settings.get("colorbar_enabled", False)
        quiver_factor = max(0.1, float(settings.get("quiver_factor", 5.0)))
        dim = settings.get("_dim_vectors", False)
        alpha = 0.18 if dim else 1.0

        if colorbar_enabled:
            cmap_name = _resolve_cmap(settings.get("colorbar_cmap", "turbo"))
            magnitude = np.sqrt(us ** 2 + vs ** 2)
            vmin, vmax = self._get_colorbar_range(
                float(np.nanmin(magnitude)),
                float(np.nanmax(magnitude)),
                settings.get("colorbar_range_mode", "Auto"),
                settings.get("colorbar_min", 0.0),
                settings.get("colorbar_max", 10.0),
            )
            ax.quiver(
                xs, ys, us, vs, magnitude,
                cmap=cmap_name,
                clim=(vmin, vmax),
                angles="xy", scale_units="xy",
                scale=1.0 / quiver_factor,
                pivot="mid",
                alpha=alpha,
            )
            return (True, cmap_name, vmin, vmax)
        else:
            color = settings.get("vector_color", "lime")
            ax.quiver(
                xs, ys, us, vs,
                color=color,
                angles="xy", scale_units="xy",
                scale=1.0 / quiver_factor,
                pivot="mid",
                alpha=alpha,
            )
            return (False, "", 0.0, 1.0)

    def _draw_vorticity(self, ax, x, y, u, v, xs, ys, settings: Dict[str, Any]) -> Tuple[bool, str, float, float]:
        from services.vorticity import compute_vorticity, METHOD_MAP

        method_display = settings.get("vorticity_method", "Central Difference")
        method_code = METHOD_MAP.get(method_display, "CDM")

        try:
            omega = compute_vorticity(x, y, u, v, method_code)
        except Exception:
            return (False, "", 0.0, 1.0)

        abs_max = float(np.nanmax(np.abs(omega))) or 1.0
        cmap_name = _resolve_cmap(settings.get("vort_cmap", "seismic"))

        vmin, vmax = self._get_colorbar_range(
            -abs_max, abs_max,
            settings.get("vort_colorbar_range_mode", "Auto"),
            settings.get("vort_colorbar_min", -5.0),
            settings.get("vort_colorbar_max", 5.0),
        )

        # Use full-resolution omega for contourf (better visual quality)
        levels = np.linspace(vmin, vmax, 21)
        try:
            ax.contourf(x, y, omega, levels=levels, cmap=cmap_name,
                        alpha=0.75, extend="both")
        except Exception:
            return (False, "", 0.0, 1.0)

        return (True, cmap_name, vmin, vmax)

    def _get_colorbar_range(
        self, data_min: float, data_max: float,
        mode: str, cb_min: float, cb_max: float,
    ) -> Tuple[float, float]:
        if mode == "Manual":
            return float(cb_min), float(cb_max)
        return data_min, data_max
