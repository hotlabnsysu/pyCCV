"""Unit tests for ui/viewer_presenter.py — stateless viewer renderer."""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ui.viewer_presenter import ViewerPresenter


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

class FakeSpine:
    def set_visible(self, v):
        pass


class FakeSpines(dict):
    def values(self):
        return [FakeSpine(), FakeSpine(), FakeSpine(), FakeSpine()]


class FakePatch:
    def set_facecolor(self, c):
        self.facecolor = c


class FakeAxes:
    def __init__(self):
        self.cleared = 0
        self.imshow_calls = []
        self.quiver_calls = []
        self.contourf_calls = []
        self.spines = FakeSpines()
        self._xlim = (0.0, 1.0)
        self._ylim = (0.0, 1.0)

    def clear(self):
        self.cleared += 1

    def set_facecolor(self, c):
        pass

    def set_xticks(self, t):
        pass

    def set_yticks(self, t):
        pass

    def get_xlim(self):
        return self._xlim

    def get_ylim(self):
        return self._ylim

    def set_xlim(self, a, b=None):
        if b is None:
            self._xlim = a
        else:
            self._xlim = (a, b)

    def set_ylim(self, a, b=None):
        if b is None:
            self._ylim = a
        else:
            self._ylim = (a, b)

    def imshow(self, *args, **kwargs):
        self.imshow_calls.append((args, kwargs))

    def quiver(self, *args, **kwargs):
        self.quiver_calls.append((args, kwargs))

    def contourf(self, *args, **kwargs):
        self.contourf_calls.append((args, kwargs))

    def set_axis_off(self):
        pass


class FakeFigure:
    def __init__(self):
        self.patch = FakePatch()

    def subplots_adjust(self, **kw):
        pass


class FakeCanvas:
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_vectors(rows=8, cols=10):
    x, y = np.meshgrid(np.arange(cols) * 16, np.arange(rows) * 16)
    u = np.ones_like(x, dtype=float) * 2.0
    v = np.ones_like(x, dtype=float) * 1.0
    return {"x": x.astype(float), "y": y.astype(float), "u": u, "v": v}


def _make_image(h=128, w=160):
    return np.random.randint(0, 256, (h, w), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRedrawEmpty:
    def test_no_data_returns_no_colorbar(self):
        p = ViewerPresenter()
        ax, fig, canvas = FakeAxes(), FakeFigure(), FakeCanvas()
        cb = p.redraw(ax, fig, canvas, None, None, None, {"display_mode": "向量"})
        assert cb == (False, "", 0.0, 1.0)

    def test_clears_axes(self):
        p = ViewerPresenter()
        ax, fig, canvas = FakeAxes(), FakeFigure(), FakeCanvas()
        p.redraw(ax, fig, canvas, None, None, None, {"display_mode": "向量"})
        assert ax.cleared >= 1


class TestRedrawVectorMode:
    def test_single_color_quiver(self):
        p = ViewerPresenter()
        ax, fig, canvas = FakeAxes(), FakeFigure(), FakeCanvas()
        vectors = _make_vectors()
        settings = {
            "display_mode": "向量",
            "grid_skip": 1,
            "colorbar_enabled": False,
            "vector_color": "lime",
            "quiver_factor": 5.0,
        }
        show_cb, cmap, vmin, vmax = p.redraw(ax, fig, canvas, None, vectors, None, settings)
        assert show_cb is False
        assert len(ax.quiver_calls) == 1

    def test_multi_color_quiver(self):
        p = ViewerPresenter()
        ax, fig, canvas = FakeAxes(), FakeFigure(), FakeCanvas()
        vectors = _make_vectors()
        settings = {
            "display_mode": "向量",
            "grid_skip": 1,
            "colorbar_enabled": True,
            "colorbar_cmap": "turbo",
            "colorbar_range_mode": "Auto",
            "colorbar_min": 0.0,
            "colorbar_max": 10.0,
            "quiver_factor": 5.0,
        }
        show_cb, cmap, vmin, vmax = p.redraw(ax, fig, canvas, None, vectors, None, settings)
        assert show_cb is True
        assert cmap == "turbo"

    def test_dim_vectors_alpha(self):
        p = ViewerPresenter()
        ax, fig, canvas = FakeAxes(), FakeFigure(), FakeCanvas()
        vectors = _make_vectors()
        settings = {
            "display_mode": "向量",
            "grid_skip": 1,
            "colorbar_enabled": False,
            "vector_color": "lime",
            "quiver_factor": 5.0,
            "_dim_vectors": True,
        }
        p.redraw(ax, fig, canvas, None, vectors, None, settings)
        _, kwargs = ax.quiver_calls[0]
        assert kwargs["alpha"] == 0.18


class TestRedrawVorticityMode:
    def test_contourf_called(self):
        p = ViewerPresenter()
        ax, fig, canvas = FakeAxes(), FakeFigure(), FakeCanvas()
        vectors = _make_vectors()
        settings = {
            "display_mode": "渦度",
            "grid_skip": 1,
            "vorticity_method": "Central Difference",
            "vort_cmap": "seismic",
            "vort_colorbar_range_mode": "Auto",
            "vort_colorbar_min": -5.0,
            "vort_colorbar_max": 5.0,
        }
        show_cb, cmap, vmin, vmax = p.redraw(ax, fig, canvas, None, vectors, None, settings)
        assert show_cb is True
        assert len(ax.contourf_calls) == 1


class TestRedrawImageMode:
    def test_imshow_called_for_image_only(self):
        p = ViewerPresenter()
        ax, fig, canvas = FakeAxes(), FakeFigure(), FakeCanvas()
        image = _make_image()
        settings = {"display_mode": "影像"}
        p.redraw(ax, fig, canvas, image, None, None, settings)
        assert len(ax.imshow_calls) == 1

    def test_image_with_vectors_extent(self):
        p = ViewerPresenter()
        ax, fig, canvas = FakeAxes(), FakeFigure(), FakeCanvas()
        image = _make_image()
        vectors = _make_vectors()
        grid_info = {"dx": 16.0, "dy": 16.0}
        settings = {
            "display_mode": "向量",
            "grid_skip": 1,
            "colorbar_enabled": False,
            "vector_color": "lime",
            "quiver_factor": 5.0,
        }
        p.redraw(ax, fig, canvas, image, vectors, grid_info, settings)
        assert len(ax.imshow_calls) == 1
        assert len(ax.quiver_calls) == 1


class TestZoomPreservation:
    def test_restores_previous_zoom(self):
        p = ViewerPresenter()
        ax, fig, canvas = FakeAxes(), FakeFigure(), FakeCanvas()
        ax._xlim = (10.0, 50.0)
        ax._ylim = (20.0, 80.0)
        image = _make_image()
        settings = {"display_mode": "影像"}
        p.redraw(ax, fig, canvas, image, None, None, settings)
        assert ax._xlim == (10.0, 50.0)
        assert ax._ylim == (20.0, 80.0)
