import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ui.plot_presenter import DisplaySettings, PlotPresenter, choose_vectors


class FakeAxes:
    def __init__(self):
        self.cleared = 0
        self.facecolor = None
        self.imshow_calls = []
        self.quiver_calls = []
        self.xlim = None
        self.ylim = None
        self.axis_off = 0
        self.xticks = None
        self.yticks = None

    def clear(self):
        self.cleared += 1

    def set_facecolor(self, color):
        self.facecolor = color

    def set_xticks(self, ticks):
        self.xticks = ticks

    def set_yticks(self, ticks):
        self.yticks = ticks

    def imshow(self, image, cmap=None):
        self.imshow_calls.append((image, cmap))

    def quiver(self, *args, **kwargs):
        self.quiver_calls.append((args, kwargs))

    def set_xlim(self, start, end):
        self.xlim = (start, end)

    def set_ylim(self, start, end):
        self.ylim = (start, end)

    def set_axis_off(self):
        self.axis_off += 1


class FakePatch:
    def __init__(self):
        self.facecolor = None

    def set_facecolor(self, color):
        self.facecolor = color


class FakeFigure:
    def __init__(self):
        self.patch = FakePatch()
        self.tight_layout_calls = []

    def tight_layout(self, pad=0):
        self.tight_layout_calls.append(pad)


class FakeCanvas:
    def __init__(self):
        self.draw_calls = 0

    def draw(self):
        self.draw_calls += 1


def _make_results():
    base = np.arange(16, dtype=float).reshape(4, 4)
    return {
        "u_raw": base + 1,
        "v_raw": base + 2,
        "u_filt": base + 3,
        "v_filt": base + 4,
        "u_interp": base + 5,
        "v_interp": base + 6,
        "u_smooth": base + 7,
        "v_smooth": base + 8,
        "u_final": base + 9,
        "v_final": base + 10,
    }


def test_choose_vectors_prefers_interp_for_filter_mode_when_available():
    settings = DisplaySettings(plot_now=2, grid_skip=1, quiver_factor=5.0, vector_color="lime")
    results = _make_results()

    u, v = choose_vectors(results, settings)

    assert np.array_equal(u, results["u_interp"])
    assert np.array_equal(v, results["v_interp"])


def test_choose_vectors_falls_back_to_filt_for_filter_mode():
    settings = DisplaySettings(plot_now=2, grid_skip=1, quiver_factor=5.0, vector_color="lime")
    results = _make_results()
    results["u_interp"] = None
    results["v_interp"] = None

    u, v = choose_vectors(results, settings)

    assert np.array_equal(u, results["u_filt"])
    assert np.array_equal(v, results["v_filt"])


def test_choose_vectors_falls_back_to_final_when_requested_stage_missing():
    settings = DisplaySettings(plot_now=3, grid_skip=1, quiver_factor=5.0, vector_color="lime")
    results = _make_results()
    results["u_smooth"] = None
    results["v_smooth"] = None

    u, v = choose_vectors(results, settings)

    assert np.array_equal(u, results["u_final"])
    assert np.array_equal(v, results["v_final"])


def test_redraw_uses_image_and_quiver_with_display_settings():
    axes = FakeAxes()
    figure = FakeFigure()
    canvas = FakeCanvas()
    presenter = PlotPresenter()
    image = np.ones((4, 6), dtype=np.uint8)
    x = np.arange(16).reshape(4, 4)
    y = np.arange(16).reshape(4, 4) + 100
    results = _make_results()
    settings = DisplaySettings(plot_now=1, grid_skip=2, quiver_factor=4.0, vector_color="red")

    presenter.redraw(axes, figure, canvas, image, (x, y, results), settings)

    assert axes.imshow_calls and axes.imshow_calls[0][1] == "gray"
    assert len(axes.quiver_calls) == 1
    quiver_args, quiver_kwargs = axes.quiver_calls[0]
    assert quiver_args[0].shape == (2, 2)
    assert quiver_args[2].shape == (2, 2)
    assert quiver_kwargs["color"] == "red"
    assert quiver_kwargs["scale"] == 0.25
    assert axes.xlim == (0, 6)
    assert axes.ylim == (4, 0)
    assert canvas.draw_calls == 1


def test_redraw_plot_now_zero_clears_canvas_without_image():
    axes = FakeAxes()
    figure = FakeFigure()
    canvas = FakeCanvas()
    presenter = PlotPresenter()
    settings = DisplaySettings(plot_now=0, grid_skip=1, quiver_factor=5.0, vector_color="lime")

    presenter.redraw(axes, figure, canvas, None, None, settings)

    assert axes.facecolor == "black"
    assert axes.imshow_calls == []
    assert axes.quiver_calls == []
    assert canvas.draw_calls == 1
