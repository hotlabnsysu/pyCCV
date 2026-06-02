"""StreamlineManager — interactive streamline overlay for the viewer canvas."""

from __future__ import annotations

from typing import Callable, Dict, Optional

import numpy as np
from PySide6.QtCore import Qt


_MAX_SEEDS = 200


class StreamlineManager:
    """Manage seed points, canvas click events, and streamline rendering."""

    def __init__(
        self,
        canvas,
        ax,
        on_changed: Callable[[], None],
    ):
        self._canvas = canvas
        self._ax = ax
        self._on_changed = on_changed
        self._seed_points: list[tuple[float, float]] = []
        self._visible: bool = True
        self._active: bool = False
        self._cid_press: Optional[int] = None
        self._cid_release: Optional[int] = None
        self._drag_start: Optional[tuple[float, float]] = None
        self._color: str = "white"
        self._line_seed_count: int = 10

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def has_seeds(self) -> bool:
        return bool(self._seed_points) and self._visible

    @property
    def color(self) -> str:
        return self._color

    @color.setter
    def color(self, value: str) -> None:
        self._color = value
        if self._seed_points and self._visible:
            self._on_changed()

    @property
    def line_seed_count(self) -> int:
        return self._line_seed_count

    @line_seed_count.setter
    def line_seed_count(self, value: int) -> None:
        self._line_seed_count = max(2, value)

    def activate(self) -> None:
        if self._active:
            return
        self._active = True
        self._cid_press = self._canvas.mpl_connect(
            "button_press_event", self._on_press,
        )
        self._cid_release = self._canvas.mpl_connect(
            "button_release_event", self._on_release,
        )
        self._canvas.setCursor(Qt.CursorShape.CrossCursor)

    def deactivate(self) -> None:
        if not self._active:
            return
        self._active = False
        self._drag_start = None
        for cid in (self._cid_press, self._cid_release):
            if cid is not None:
                self._canvas.mpl_disconnect(cid)
        self._cid_press = None
        self._cid_release = None
        self._canvas.unsetCursor()

    def show(self) -> None:
        self._visible = True
        self._on_changed()

    def hide(self) -> None:
        self._visible = False
        self._on_changed()

    def clear(self) -> None:
        self._seed_points.clear()
        self._visible = True
        self.deactivate()
        self._on_changed()

    def draw(self, ax, vectors: Dict[str, np.ndarray]) -> None:
        if not self._seed_points or not self._visible:
            return

        x = vectors["x"]
        y = vectors["y"]
        u = vectors["u"]
        v = vectors["v"]

        x_1d = x[0, :]
        y_1d = y[:, 0]

        flip_y = y_1d.size > 1 and y_1d[1] < y_1d[0]
        if flip_y:
            y_1d = y_1d[::-1]
            u = u[::-1, :]
            v = v[::-1, :]

        flip_x = x_1d.size > 1 and x_1d[1] < x_1d[0]
        if flip_x:
            x_1d = x_1d[::-1]
            u = u[:, ::-1]
            v = v[:, ::-1]

        seeds = np.array(self._seed_points)

        try:
            ax.streamplot(
                x_1d, y_1d, u, v,
                start_points=seeds,
                color=self._color,
                linewidth=1.2,
                arrowsize=1.0,
                arrowstyle="-|>",
                integration_direction="both",
                broken_streamlines=False,
            )
        except Exception:
            pass

        ax.plot(
            seeds[:, 0], seeds[:, 1],
            "o",
            color="#FF4444",
            markersize=5,
            markeredgecolor="white",
            markeredgewidth=0.8,
            zorder=10,
        )

    def _on_press(self, event) -> None:
        if event.inaxes is not self._ax or event.button != 1:
            return
        self._drag_start = (event.xdata, event.ydata)

    def _on_release(self, event) -> None:
        if event.inaxes is not self._ax or event.button != 1:
            self._drag_start = None
            return
        if self._drag_start is None:
            return

        x0, y0 = self._drag_start
        x1, y1 = event.xdata, event.ydata
        self._drag_start = None

        dist = np.hypot(x1 - x0, y1 - y0)
        xlim = self._ax.get_xlim()
        ylim = self._ax.get_ylim()
        diag = np.hypot(xlim[1] - xlim[0], ylim[1] - ylim[0])
        threshold = diag * 0.01

        if dist < threshold:
            self._seed_points.append((x1, y1))
        else:
            n = self._line_seed_count
            for i in range(n):
                t = i / (n - 1)
                self._seed_points.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))

        if len(self._seed_points) > _MAX_SEEDS:
            self._seed_points = self._seed_points[-_MAX_SEEDS:]

        self._on_changed()
