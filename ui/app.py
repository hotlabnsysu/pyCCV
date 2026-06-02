
import logging
from pathlib import Path
from typing import Dict, List, Tuple

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QProgressBar, QTextEdit,
    QStackedWidget, QSizePolicy, QMessageBox,
    QScrollArea
)
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QCloseEvent

from services.settings import SettingsService
from services.settings_validation import normalize_interrogation_areas
from services.analysis import AnalysisService
from services.convert_service import ConvertService
from services.logger import logger, attach_qt_handler
from .logging_qt import QtLogHandler
from .controller import MainWindowController
from .plot_presenter import DisplaySettings, PlotPresenter
from .viewer_view_controller import ViewerViewController
from .convert_view_controller import ConvertViewController
from .tabs.basic_settings import BasicSettingsTab
from .tabs.piv_settings import PivSettingsTab
from .tabs.viewer import ViewerTab
from .tabs.convert import ConvertTab


class PyCCVMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("pyCCV")
        self.resize(1280, 720)

        # Services
        self.settings_service = SettingsService()
        self.analysis_service = AnalysisService()
        self.convert_service = ConvertService()
        self.controller = MainWindowController(
            view=self,
            settings_service=self.settings_service,
            analysis_service=self.analysis_service,
        )

        # UI State
        self._last_image = None
        self._last_vectors = None
        self._is_closing = False
        self.plot_presenter = PlotPresenter()
        self._active_display: str = "analysis"   # "analysis" | "viewer" | "convert"

        # Wire analysis signals (queued connection: cross-thread safe)
        self.analysis_service.progress.connect(self._on_progress)
        self.analysis_service.result.connect(self._on_result)
        self.analysis_service.completed.connect(self._on_complete)
        self.analysis_service.pair_error.connect(self._on_pair_error)

        self._create_ui()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _create_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(5, 5, 5, 5)
        root_layout.setSpacing(5)

        # Left panel (stretch=2), Right panel (stretch=3)
        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        root_layout.addWidget(left_panel, stretch=2)
        root_layout.addWidget(right_panel, stretch=1)

    def _build_left_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # ── Display stack (analysis / viewer / service) ───────────────
        self._display_stack = QStackedWidget()

        # Page 0: Analysis canvas (基本設定 / PIV 設定)
        self.fig = Figure(figsize=(5, 4), dpi=100, facecolor='#2b2b2b')
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor('#2b2b2b')
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_visible(False)
        self.fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

        self._copyright_text = self.ax.text(
            0.5, 0.5,
            "© Hydrodynamics & Ocean Technology Laboratory (HOTLAB)\n"
            "National Sun Yat-sen University\n"
            "MIT-style License  ·  Non-Commercial  ·  Research Use Only",
            transform=self.ax.transAxes,
            ha="center", va="center",
            color="#686868", fontsize=9,
            multialignment="center", linespacing=1.9,
            fontfamily="sans-serif",
        )

        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._display_stack.addWidget(self.canvas)                # index 0

        # Page 1: Viewer canvas (VIEW)
        self.viewer_fig = Figure(figsize=(5, 4), dpi=100, facecolor='#2b2b2b')
        self.viewer_ax = self.viewer_fig.add_subplot(111)
        self.viewer_ax.set_facecolor('#2b2b2b')
        self.viewer_ax.set_xticks([])
        self.viewer_ax.set_yticks([])
        for spine in self.viewer_ax.spines.values():
            spine.set_visible(False)
        self.viewer_fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
        self.viewer_ax.set_aspect('equal', adjustable='box')

        self.viewer_canvas = FigureCanvasQTAgg(self.viewer_fig)
        self.viewer_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._display_stack.addWidget(self.viewer_canvas)         # index 1

        # Page 2: Empty (SERVICE — no display content)
        _service_page = QWidget()
        _service_page.setStyleSheet("background: #2b2b2b;")
        self._display_stack.addWidget(_service_page)              # index 2

        layout.addWidget(self._display_stack, stretch=1)

        # Log area (inside a card)
        self.log_card = QWidget()
        self.log_card.setProperty("card", True)
        log_layout = QVBoxLayout(self.log_card)
        log_layout.setContentsMargins(6, 4, 6, 4)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(100)
        self.log_box.setProperty("variant", "log")
        # Keep UI responsive on very long runs — auto-trim oldest blocks.
        self.log_box.document().setMaximumBlockCount(1000)
        log_layout.addWidget(self.log_box)

        layout.addWidget(self.log_card)

        # Install Qt log handler AFTER log_box exists. INFO+ filter so DEBUG
        # stays out of the UI but still reaches console / rotating file.
        self._qt_log_handler = QtLogHandler()
        self._qt_log_handler.log_emitted.connect(self._append_log_html)
        attach_qt_handler(self._qt_log_handler, level=logging.INFO)

        logger.info("系統已啟動，等待操作")
        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Button bar: Stop | Pause | Start
        btn_bar = QWidget()
        btn_layout = QHBoxLayout(btn_bar)
        btn_layout.setContentsMargins(6, 6, 6, 6)
        btn_layout.setSpacing(8)

        self.btn_stop = QPushButton("停止")
        self.btn_stop.setProperty("role", "danger")
        self.btn_stop.setFixedHeight(26)
        self.btn_stop.clicked.connect(self._on_stop)
        btn_layout.addWidget(self.btn_stop)

        btn_layout.addStretch()

        self.btn_pause = QPushButton("暫停")
        self.btn_pause.setProperty("role", "warning")
        self.btn_pause.setFixedHeight(26)
        self.btn_pause.clicked.connect(self._on_pause)
        btn_layout.addWidget(self.btn_pause)

        self.btn_start = QPushButton("開始分析")
        self.btn_start.setProperty("role", "success")
        self.btn_start.setFixedHeight(26)
        self.btn_start.clicked.connect(self._on_start)
        btn_layout.addWidget(self.btn_start)

        layout.addWidget(btn_bar)

        # Tab row
        tab_row = QWidget()
        tab_row_layout = QHBoxLayout(tab_row)
        tab_row_layout.setContentsMargins(5, 0, 5, 0)
        tab_row_layout.setSpacing(2)

        self._tab_buttons = []
        tab_names = ["基本設定", "PIV 設定", "VIEW", "SERVICE"]
        for i, name in enumerate(tab_names):
            btn = QPushButton(name)
            btn.setProperty("role", "tab")
            btn.setCheckable(True)
            btn.setFixedHeight(24)
            btn.clicked.connect(lambda checked, idx=i: self._switch_tab(idx))
            tab_row_layout.addWidget(btn)
            self._tab_buttons.append(btn)
        tab_row_layout.addStretch()   # tabs hug left, no stretching

        layout.addWidget(tab_row)

        # Stacked widget for tab pages
        self._tab_stack = QStackedWidget()

        # Instantiate tabs
        self.tab_basic = BasicSettingsTab(self.settings_service.get("basic"))
        self.tab_piv = PivSettingsTab(
            self.settings_service.get("piv"),
            self.settings_service.get("postproc"),
        )
        self.tab_viewer = ViewerTab(
            self.settings_service.get("viewer"),
        )
        self.tab_convert = ConvertTab(self.settings_service.get("convert"))

        # Wrap each tab in a scroll area for resize safety
        for tab in [self.tab_basic, self.tab_piv, self.tab_viewer, self.tab_convert]:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(tab)
            self._tab_stack.addWidget(scroll)

        layout.addWidget(self._tab_stack, stretch=1)

        # ── Progress card — pinned to bottom, outside tab stack ────────
        self.prog_card = QWidget()
        prog_card = self.prog_card
        prog_card.setProperty("card", True)
        prog_layout = QVBoxLayout(prog_card)
        prog_layout.setContentsMargins(10, 6, 10, 8)
        prog_layout.setSpacing(3)

        _prog_label_css = "font-size: 12px;"

        self.current_file_label = QLabel("")
        self.current_file_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.current_file_label.setStyleSheet(_prog_label_css)
        prog_layout.addWidget(self.current_file_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)
        prog_layout.addWidget(self.progress_bar)

        status_row = QHBoxLayout()
        self.progress_text = QLabel("準備就緒")
        self.progress_text.setStyleSheet(_prog_label_css)
        self.time_info_label = QLabel("剩餘時間: --:--:--")
        self.time_info_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.time_info_label.setStyleSheet(_prog_label_css)
        status_row.addWidget(self.progress_text)
        status_row.addWidget(self.time_info_label)
        prog_layout.addLayout(status_row)

        layout.addWidget(prog_card)

        # Connect plot params changed signal from basic tab
        self.tab_basic.plot_params_changed.connect(self._on_display_settings_changed)

        # Viewer control signals
        # Viewer and Convert view controllers (own all tab-specific logic)
        self._viewer_vc = ViewerViewController(
            self.viewer_ax, self.viewer_fig, self.viewer_canvas,
            self.tab_viewer.cb_fig, self.tab_viewer.cb_canvas,
            self.tab_viewer, self.settings_service,
        )
        self._convert_vc = ConvertViewController(
            self, self.tab_convert, self.convert_service,
        )

        # Activate first tab
        self._switch_tab(0)

        return panel

    def _switch_tab(self, index: int):
        prev_display = self._active_display
        self._tab_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_buttons):
            btn.setChecked(i == index)

        if prev_display == "viewer" and index != 2:
            self._viewer_vc.on_tab_leave()

        if index == 2:
            self._display_stack.setCurrentIndex(1)
            self.log_card.setVisible(True)
            self.prog_card.setVisible(False)
            self._active_display = "viewer"
            self.btn_start.setText("掃描檔案")
            self.btn_pause.setText("繪圖")
            self.btn_stop.setText("清除")
            self._viewer_vc.on_tab_enter()
        elif index == 3:
            self._display_stack.setCurrentIndex(2)
            self.log_card.setVisible(True)
            self.prog_card.setVisible(True)
            self._active_display = "convert"
            self.btn_start.setText("開始轉換")
            self.btn_pause.setText("暫停")
            self.btn_stop.setText("停止")
        else:
            self._display_stack.setCurrentIndex(0)
            self.log_card.setVisible(True)
            self.prog_card.setVisible(True)
            self._active_display = "analysis"
            self.btn_start.setText("開始分析")
            self.btn_pause.setText("暫停")
            self.btn_stop.setText("停止")
            if self._last_image is not None or self._last_vectors is not None:
                self._redraw_display()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------

    @Slot(str)
    def _append_log_html(self, html: str):
        if self._is_closing:
            return
        try:
            self.log_box.append(html)
            self.log_box.ensureCursorVisible()
        except Exception:
            pass

    def _set_closing_state(self, closing: bool):
        self._is_closing = closing

    # ------------------------------------------------------------------
    # Settings Gathering
    # ------------------------------------------------------------------

    def _update_settings_from_ui(self):
        basic_vals = self.tab_basic.get_values()
        piv_vals = self.tab_piv.get_values()
        post_vals = self.tab_piv.get_postproc_values()
        viewer_vals = self.tab_viewer.get_values()
        convert_vals = self.tab_convert.get_values()

        self.settings_service.merge("basic", basic_vals)

        # Validate int areas before merging
        int_areas_raw = [piv_vals.get(f"int_area_{i}", "none") for i in range(1, 7)]
        normalized_areas, num_passes, error_msg = normalize_interrogation_areas(int_areas_raw)
        if error_msg:
            # Suppress the modal dialog while the window is being closed —
            # otherwise it blocks shutdown. Skip the bad piv section instead so
            # the other tabs still persist.
            if self._is_closing:
                logger.warning("關閉時 PIV int_area 設定無效，略過該區段: %s", error_msg)
            else:
                QMessageBox.critical(self, "設定錯誤", error_msg)
                raise ValueError(error_msg)
        else:
            piv_update = dict(piv_vals)
            piv_update["num_passes"] = num_passes
            for i, val in enumerate(normalized_areas, start=1):
                piv_update[f"int_area_{i}"] = val
            self.settings_service.merge("piv", piv_update)

        self.settings_service.merge("postproc", post_vals)
        self.settings_service.merge("viewer", viewer_vals)
        self.settings_service.merge("convert", convert_vals)

    # ------------------------------------------------------------------
    # Analysis Control
    # ------------------------------------------------------------------

    def _on_start(self):
        if self._active_display == "viewer":
            self.tab_viewer.scan_requested.emit()
        elif self._active_display == "convert":
            self._convert_vc.start()
        else:
            self.controller.handle_start()

    def _on_stop(self):
        if self._active_display == "viewer":
            self.tab_viewer.clear_view()
        elif self._active_display == "convert":
            self._convert_vc.stop()
        else:
            self.controller.handle_stop()

    def _on_pause(self):
        if self._active_display == "viewer":
            self.tab_viewer.plot_requested.emit()
        elif self._active_display == "convert":
            self._convert_vc.pause()
        else:
            self.controller.handle_pause()

    def _on_display_settings_changed(self):
        self.controller.handle_display_settings_changed()

    # ------------------------------------------------------------------
    # Signal Handlers (called on main thread via Qt queued connection)
    # ------------------------------------------------------------------

    @Slot(int, int, float)
    def _on_progress(self, current: int, total: int, remaining: float):
        if self._is_closing:
            return
        pct = current / total
        self.progress_bar.setValue(int(pct * 1000))
        self.progress_text.setText(f"進度 {pct*100:.1f}% ({current}/{total})")

        m, s = divmod(int(remaining), 60)
        h, m = divmod(m, 60)
        d, h = divmod(h, 24)
        rem_str = f"{d:02d}:{h:02d}:{m:02d}:{s:02d}"
        self.time_info_label.setText(f"剩餘: {rem_str}")

    @Slot(object, object, object, object, object)
    def _on_result(self, x, y, results, img, file_path):
        if self._is_closing:
            return
        self._last_image = img
        self._last_vectors = (x, y, results)

        if file_path:
            self.current_file_label.setText(Path(file_path).name)

        # Only update canvas when in analysis mode
        if self._active_display != "analysis":
            return

        # Hide copyright watermark on first result
        if self._copyright_text is not None:
            self._copyright_text.set_visible(False)
            self._copyright_text = None

        self._redraw_display()

    @Slot(str, bool)
    def _on_complete(self, total_time_str: str, cancelled: bool):
        if self._is_closing:
            return
        self.btn_start.setEnabled(True)
        self.btn_pause.setText("暫停")
        if cancelled:
            self.progress_text.setText(f"已停止 ({total_time_str})")
        else:
            self.progress_text.setText(f"完成! ({total_time_str})")
            QMessageBox.information(self, "完成", f"分析已完成\n總耗時: {total_time_str}")

    @Slot(int, str, str)
    def _on_pair_error(self, pair_idx: int, filename: str, error_msg: str):
        if self._is_closing:
            return
        logger.warning("影像對處理失敗 | #%d | %s | %s", pair_idx, filename, error_msg)

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def _redraw_display(self):
        try:
            basic_vals = self.tab_basic.get_values()
            display_settings = DisplaySettings(
                plot_now=basic_vals.get("plot_now", 3),
                grid_skip=basic_vals.get("grid_skip", 1),
                quiver_factor=basic_vals.get("quiver_factor", 5.0),
                vector_color=basic_vals.get("vector_color", "lime"),
            )
        except Exception as exc:
            logger.debug("讀取重繪參數失敗: %s", exc)
            display_settings = DisplaySettings(
                plot_now=3,
                grid_skip=1,
                quiver_factor=5.0,
                vector_color="lime",
            )

        self.plot_presenter.redraw(
            self.ax,
            self.fig,
            self.canvas,
            self._last_image,
            self._last_vectors,
            display_settings,
        )

    # ------------------------------------------------------------------
    # Window Close
    # ------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent):
        self._is_closing = True
        # Each save call is independent — one failing must not prevent the
        # others from running. Without per-call guards, an exception on the
        # first save dropped the user's other unsaved tabs.
        if hasattr(self, "_viewer_vc"):
            try:
                self._viewer_vc.set_closing(True)
                self._viewer_vc.save_settings()
            except Exception:
                logger.exception("關閉時儲存 viewer 設定失敗")
        if hasattr(self, "_convert_vc"):
            try:
                self._convert_vc.set_closing(True)
            except Exception:
                logger.exception("關閉時通知 convert view-controller 失敗")
        if hasattr(self, "tab_convert"):
            try:
                self.settings_service.merge("convert", self.tab_convert.get_values())
            except Exception:
                logger.exception("關閉時合併 convert 設定失敗")
        if self.controller.handle_close_request():
            try:
                self._convert_vc.shutdown()
            except Exception:
                logger.exception("關閉時 convert 服務 shutdown 失敗")
            event.accept()
            return
        self._is_closing = False
        if hasattr(self, "_viewer_vc"):
            self._viewer_vc.set_closing(False)
        if hasattr(self, "_convert_vc"):
            self._convert_vc.set_closing(False)
        event.ignore()



