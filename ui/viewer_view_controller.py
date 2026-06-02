"""ViewerViewController — owns viewer tab logic, playback, and streamlines."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image as PILImage
import matplotlib.cm as mplcm
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
from PySide6.QtCore import QTimer

from services.logger import logger
from .viewer_presenter import ViewerPresenter
from .streamline_manager import StreamlineManager
from services.viewer_files import ViewerFileService


class ViewerViewController:
    """Extracts viewer logic from PyCCVMainWindow."""

    def __init__(self, ax, fig, canvas, cb_fig, cb_canvas, tab_viewer, settings_service):
        self._ax = ax
        self._fig = fig
        self._canvas = canvas
        self._cb_fig = cb_fig
        self._cb_canvas = cb_canvas
        self._tab = tab_viewer
        self._settings_service = settings_service

        self._presenter = ViewerPresenter()
        self._file_service = ViewerFileService()
        self._streamline_mgr = StreamlineManager(canvas, ax, on_changed=self.redraw)

        self._file_pairs: List[Tuple] = []
        self._vorticity_cache: Dict = {}
        self._is_closing = False
        self._cb_state: Tuple[bool, str, float, float] | None = None

        self._play_timer = QTimer()
        self._play_timer.setInterval(200)
        self._play_timer.timeout.connect(self._viewer_advance)

        self._tab.scan_requested.connect(self._on_scan)
        self._tab.plot_requested.connect(self.redraw)
        self._tab.display_changed.connect(self.redraw)
        self._tab.play_toggled.connect(self._on_play_toggled)
        self._tab.streamline_toggled.connect(self._on_streamline_toggled)
        self._tab.streamline_clear.connect(self._streamline_mgr.clear)
        self._tab.streamline_visibility.connect(
            lambda show: self._streamline_mgr.show() if show else self._streamline_mgr.hide()
        )
        self._tab.streamline_color_changed.connect(
            lambda c: setattr(self._streamline_mgr, "color", c)
        )
        self._tab.streamline_count_changed.connect(
            lambda n: setattr(self._streamline_mgr, "line_seed_count", n)
        )

    def set_closing(self, v: bool) -> None:
        self._is_closing = v

    # ------------------------------------------------------------------
    # Tab enter / leave
    # ------------------------------------------------------------------

    def on_tab_enter(self) -> None:
        self.redraw()

    def on_tab_leave(self) -> None:
        self._tab.stop_playback()
        self._play_timer.stop()
        self._cb_canvas.setVisible(False)
        self._streamline_mgr.deactivate()
        self._tab.deactivate_streamline()

    # ------------------------------------------------------------------
    # Scan
    # ------------------------------------------------------------------

    def _on_scan(self) -> None:
        viewer_vals = self._tab.get_values()
        vector_dir = viewer_vals.get("vector_dir", "")
        image_dir = viewer_vals.get("image_dir", "")
        if not vector_dir:
            logger.warning("VIEWER: 請先選取向量目錄")
            return
        try:
            pairs = self._file_service.scan_pairs(vector_dir, image_dir or None)
        except Exception as exc:
            logger.error("VIEWER: 掃描失敗 | 原因=%s", exc)
            pairs = []
        self._file_pairs = pairs
        self._vorticity_cache.clear()
        self._tab.update_pair_count(len(pairs))
        logger.info("VIEWER: 掃描到 %d 個向量檔案對", len(pairs))
        if pairs:
            self._tab.set_current_pair(1)
            self.redraw()

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def _on_play_toggled(self, playing: bool) -> None:
        if playing:
            self._play_timer.start()
        else:
            self._play_timer.stop()

    def _viewer_advance(self) -> None:
        if not self._file_pairs:
            self._play_timer.stop()
            return
        self._tab._navigate(+1)

    # ------------------------------------------------------------------
    # Streamline
    # ------------------------------------------------------------------

    def _on_streamline_toggled(self, active: bool) -> None:
        if active:
            self._streamline_mgr.activate()
        else:
            self._streamline_mgr.deactivate()

    # ------------------------------------------------------------------
    # Redraw
    # ------------------------------------------------------------------

    def redraw(self) -> None:
        if self._is_closing:
            return
        if not self._file_pairs:
            self._ax.clear()
            self._ax.set_facecolor("#1a1a1a")
            self._ax.set_xticks([])
            self._ax.set_yticks([])
            for spine in self._ax.spines.values():
                spine.set_visible(False)
            self._canvas.draw()
            self._cb_canvas.setVisible(False)
            return

        viewer_vals = self._tab.get_values()
        s_viewer = self._settings_service.get("viewer")
        s_viewer.update(viewer_vals)

        pair_idx = self._tab.get_current_pair() - 1
        pair_idx = max(0, min(pair_idx, len(self._file_pairs) - 1))
        vector_path, img1_path, _ = self._file_pairs[pair_idx]

        try:
            vectors, grid_info = self._load_vectors(vector_path)
        except Exception as exc:
            logger.error("VIEWER: 讀取向量失敗 | 檔案=%s | 原因=%s", vector_path.name, exc)
            return

        image = None
        if img1_path and img1_path.is_file():
            try:
                pil_img = PILImage.open(img1_path)
                image = np.array(pil_img)
            except Exception:
                image = None

        if viewer_vals.get("display_mode") == "向量" and self._streamline_mgr.has_seeds:
            viewer_vals["_dim_vectors"] = True

        cb_info = self._presenter.redraw(
            self._ax, self._fig, self._canvas,
            image, vectors, grid_info, viewer_vals,
        )

        if vectors is not None:
            self._streamline_mgr.draw(self._ax, vectors)

        self._canvas.draw()
        self._update_colorbar(*cb_info)

    def _update_colorbar(self, show: bool, cmap: str, vmin: float, vmax: float) -> None:
        if not show:
            self._cb_canvas.setVisible(False)
            self._cb_state = None
            return
        new_state = (show, cmap, vmin, vmax)
        if new_state == self._cb_state:
            self._cb_canvas.setVisible(True)
            return
        self._cb_state = new_state
        self._cb_fig.clear()
        self._cb_fig.set_facecolor("#2b2b2b")
        cb_ax = self._cb_fig.add_axes([0.02, 0.58, 0.96, 0.34])
        cb_ax.set_facecolor("#2b2b2b")
        sm = ScalarMappable(norm=Normalize(vmin=vmin, vmax=vmax), cmap=mplcm.get_cmap(cmap))
        sm.set_array([])
        cb = self._cb_fig.colorbar(sm, cax=cb_ax, orientation="horizontal")
        cb.ax.tick_params(labelsize=7, colors="#CCCCCC")
        cb.outline.set_edgecolor("#555555")
        self._cb_canvas.draw()
        self._cb_canvas.setVisible(True)

    # ------------------------------------------------------------------
    # Vector loading
    # ------------------------------------------------------------------

    def _load_vectors(self, vector_path: Path):
        from shared.io_formats import load_npz, load_mat, load_raw_custom, load_flo

        suffix = vector_path.suffix.lower()
        if suffix == ".npz":
            data = load_npz(vector_path)
        elif suffix == ".mat":
            data = load_mat(vector_path)
        elif suffix == ".raw":
            data = load_raw_custom(vector_path)
        elif suffix == ".flo":
            data = load_flo(vector_path, with_grid=True)
        else:
            raise ValueError(f"Unsupported vector format: {suffix}")

        x = data.get("x")
        y = data.get("y")
        u = data.get("u")
        v = data.get("v")

        if u is None or v is None:
            raise ValueError("Vector data missing 'u' or 'v'")

        if u.ndim == 1:
            n = u.size
            ny = int(np.round(np.sqrt(n)))
            nx = n // ny
            u = u.reshape(ny, nx)
            v = v.reshape(ny, nx)
            if x is not None and x.ndim == 1:
                x = x.reshape(ny, nx)
            if y is not None and y.ndim == 1:
                y = y.reshape(ny, nx)

        if x is None:
            h, w = u.shape
            xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
            x, y = xx, yy

        if y is None:
            h, w = u.shape
            xx, yy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
            x, y = xx, yy

        vectors = {"x": x, "y": y, "u": u, "v": v}

        dx = float(np.median(np.diff(x[0, :]))) if x.shape[1] > 1 else 1.0
        dy = float(np.median(np.diff(y[:, 0]))) if y.shape[0] > 1 else 1.0
        if dx == 0:
            dx = 1.0
        if dy == 0:
            dy = 1.0
        grid_info = {"dx": abs(dx), "dy": abs(dy)}

        return vectors, grid_info

    def save_settings(self) -> None:
        s_viewer = self._settings_service.get("viewer")
        s_viewer.update(self._tab.get_values())
