"""ViewerTab — VIEWER 頁籤, 含三張卡片:

    1. 檔案選取
    2. 播放
    3. 繪圖模式
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QSlider, QSpinBox, QDoubleSpinBox,
    QButtonGroup, QRadioButton, QFileDialog, QStackedWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QIntValidator, QDoubleValidator, QIcon

from config import SUPPORTED_IMAGE_FORMATS
from .._card_helper import _card
from ..widgets import (
    CenteredComboBox, COMBO_QSS, SPIN_QSS, form_row,
    make_clear_btn, style_path_field,
    shorten_path as _shorten_path, set_path_field as _set_path_field,
)
from ..tokens import (
    FIELD_H as _FIELD_H,
    INPUT_SM,
    INPUT_MD,
    INPUT_LG,
    SLIDER_W,
    RANGE_EDIT_W,
    CARD_SPACING,
    OUTER_MARGIN,
    ROW_SPACING,
    LABEL_GAP,
)

_ICON_PLAY  = str(Path(__file__).parent.parent.parent / "assets" / "icons" / "ic_play.svg")
_ICON_PAUSE = str(Path(__file__).parent.parent.parent / "assets" / "icons" / "ic_pause.svg")
_PLAY_ICON_SIZE = QSize(11, 13)

# Per-card label column widths
_FILE_LABEL_W = 44     # 圖像 / 向量 (2 chinese chars)
_VORT_LABEL_W = 44     # 方法 / 色盤 (2 chinese chars)
_VEC_LABEL_W = 64      # 間隔大小 / 向量縮放 (4 chinese chars)

_PLOT_MODE_BTN_H = 36     # 繪圖模式按鈕高度 (影像/向量/渦度/流線)

_VECTOR_COLORS = ["lime", "red", "blue", "yellow", "cyan", "magenta", "white", "black"]
_COLORMAP_OPTIONS = ["plasma", "hsv", "rainbow", "jet", "turbo"]
_VORT_COLORMAP_OPTIONS = ["seismic", "RdBu"]
_VORT_METHODS = ["Central Difference", "Stokes' Theorem", "Least Squares"]


class ViewerTab(QWidget):
    """VIEWER 頁籤 — 四張控制卡片."""

    scan_requested = Signal()       # 「掃描檔案」按下
    plot_requested = Signal()       # 「繪圖」或 pair/display_mode 變更
    play_toggled = Signal(bool)     # True=開始播放, False=暫停
    display_changed = Signal()      # 任何影響顯示的設定變動 (30ms debounce)
    streamline_toggled = Signal(bool)    # True=啟用流線模式, False=停用
    streamline_clear = Signal()          # 刪除所有流線
    streamline_visibility = Signal(bool) # True=顯示, False=隱藏
    streamline_color_changed = Signal(str)  # 新顏色 hex
    streamline_count_changed = Signal(int)  # 拖曳線上釋放點個數

    def __init__(
        self,
        viewer_settings: Dict[str, Any],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.viewer_settings = viewer_settings

        self._total_pairs: int = 0
        self._is_playing: bool = False
        self._colorbar_mode: str = "single"   # "single" | "multi"

        # File card: track dir vs. multi-file mode independently for image and vector
        self._image_mode: str = "dir"
        self._vector_mode: str = "dir"
        self._image_full_path: str = viewer_settings.get("image_dir", "")
        self._vector_full_path: str = viewer_settings.get("vector_dir", "")
        self._image_custom_files: list = []
        self._vector_custom_files: list = []

        # Debounce timer for display_changed
        self._redraw_timer = QTimer(self)
        self._redraw_timer.setSingleShot(True)
        self._redraw_timer.setInterval(30)
        self._redraw_timer.timeout.connect(self.display_changed.emit)

        self._create_widgets()

    # ------------------------------------------------------------------
    # Widget Creation
    # ------------------------------------------------------------------

    def _create_widgets(self):
        font = self.font()
        font.setPixelSize(12)
        self.setFont(font)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(*OUTER_MARGIN)
        outer.setSpacing(CARD_SPACING)

        outer.addWidget(self._build_file_card())
        outer.addWidget(self._build_playback_card())
        outer.addWidget(self._build_plot_mode_card())

        self.cb_fig = Figure(figsize=(5, 0.3), dpi=100, facecolor="#2b2b2b")
        self.cb_canvas = FigureCanvasQTAgg(self.cb_fig)
        self.cb_canvas.setFixedHeight(34)
        self.cb_canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.cb_canvas.setVisible(False)
        outer.addWidget(self.cb_canvas)

        outer.addStretch()

    # ── Card 1: 檔案選取 ──────────────────────────────────────────────

    def _build_file_card(self) -> QWidget:
        card, layout = _card("檔案選取")

        # ── 圖像 row ──────────────────────────────────────────────────
        _saved_img = self.viewer_settings.get("image_custom_files", [])
        if self.viewer_settings.get("image_custom_enabled", False) and _saved_img:
            self._image_mode = "files"
            self._image_custom_files = list(_saved_img)
            _img_display = f"{len(_saved_img)} 個檔案"
        else:
            self._image_mode = "dir"
            _img_display = _shorten_path(self._image_full_path)

        self.image_dir_edit = self._make_path_field(_img_display, placeholder="點擊選取圖像目錄")
        self.image_dir_edit.setToolTip(self._image_full_path)
        self.image_dir_edit.mousePressEvent = lambda e: self._browse_image_dir()

        self._btn_image_files = QPushButton("選檔")
        self._btn_image_files.setFixedSize(38, _FIELD_H)
        self._btn_image_files.setToolTip("選取影像檔案 (可多選)")
        self._btn_image_files.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_image_files.setProperty("variant", "select")
        self._btn_image_files.clicked.connect(self._browse_image_files)

        self._btn_clear_image = self._make_clear_btn()
        self._btn_clear_image.setVisible(bool(self.image_dir_edit.text()))
        self._btn_clear_image.clicked.connect(self._clear_image_dir)
        self.image_dir_edit.textChanged.connect(
            lambda t: self._btn_clear_image.setVisible(bool(t))
        )

        _lbl_img = QLabel("圖像")
        _lbl_img.setFixedWidth(_FILE_LABEL_W)
        _lbl_img.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        img_row = QHBoxLayout()
        img_row.setSpacing(LABEL_GAP)
        img_row.addWidget(_lbl_img, 0, Qt.AlignmentFlag.AlignVCenter)
        img_row.addWidget(self.image_dir_edit, stretch=1)
        img_row.addWidget(self._btn_image_files, 0, Qt.AlignmentFlag.AlignVCenter)
        img_row.addWidget(self._btn_clear_image, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(img_row)

        # ── 向量 row ──────────────────────────────────────────────────
        _saved_vec = self.viewer_settings.get("vector_custom_files", [])
        if self.viewer_settings.get("vector_custom_enabled", False) and _saved_vec:
            self._vector_mode = "files"
            self._vector_custom_files = list(_saved_vec)
            _vec_display = f"{len(_saved_vec)} 個檔案"
        else:
            self._vector_mode = "dir"
            _vec_display = _shorten_path(self._vector_full_path)

        self.vector_dir_edit = self._make_path_field(_vec_display, placeholder="點擊選取向量目錄")
        self.vector_dir_edit.setToolTip(self._vector_full_path)
        self.vector_dir_edit.mousePressEvent = lambda e: self._browse_vector_dir()

        self._btn_vector_files = QPushButton("選檔")
        self._btn_vector_files.setFixedSize(38, _FIELD_H)
        self._btn_vector_files.setToolTip("選取向量檔案 (可多選)")
        self._btn_vector_files.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_vector_files.setProperty("variant", "select")
        self._btn_vector_files.clicked.connect(self._browse_vector_files)

        self._btn_clear_vector = self._make_clear_btn()
        self._btn_clear_vector.setVisible(bool(self.vector_dir_edit.text()))
        self._btn_clear_vector.clicked.connect(self._clear_vector_dir)
        self.vector_dir_edit.textChanged.connect(
            lambda t: self._btn_clear_vector.setVisible(bool(t))
        )

        _lbl_vec = QLabel("向量")
        _lbl_vec.setFixedWidth(_FILE_LABEL_W)
        _lbl_vec.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vec_row = QHBoxLayout()
        vec_row.setSpacing(LABEL_GAP)
        vec_row.addWidget(_lbl_vec, 0, Qt.AlignmentFlag.AlignVCenter)
        vec_row.addWidget(self.vector_dir_edit, stretch=1)
        vec_row.addWidget(self._btn_vector_files, 0, Qt.AlignmentFlag.AlignVCenter)
        vec_row.addWidget(self._btn_clear_vector, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(vec_row)

        return card

    # ── File-card helpers ─────────────────────────────────────────────

    @staticmethod
    def _make_path_field(text: str, placeholder: str) -> QLineEdit:
        field = QLineEdit(text)
        style_path_field(field)
        field.setPlaceholderText(placeholder)
        return field

    _make_clear_btn = staticmethod(make_clear_btn)

    def _browse_image_dir(self):
        start = self._image_full_path if self._image_mode == "dir" else ""
        path = QFileDialog.getExistingDirectory(self, "選擇圖像目錄", start)
        if path:
            self._image_mode = "dir"
            self._image_full_path = path
            self._image_custom_files = []
            _set_path_field(self.image_dir_edit, path)
            self.image_dir_edit.setPlaceholderText("點擊選取圖像目錄")

    def _browse_image_files(self):
        ext_list = " ".join([f"*{fmt}" for fmt in SUPPORTED_IMAGE_FORMATS])
        start = (
            str(Path(self._image_custom_files[0]).parent)
            if self._image_mode == "files" and self._image_custom_files
            else ""
        )
        files, _ = QFileDialog.getOpenFileNames(
            self, "選取圖像檔案", start,
            f"影像檔案 ({ext_list});;所有檔案 (*.*)"
        )
        if files:
            self._image_mode = "files"
            self._image_custom_files = list(files)
            self.image_dir_edit.setReadOnly(False)
            self.image_dir_edit.setText(f"{len(files)} 個檔案")
            self.image_dir_edit.setReadOnly(True)

    def _clear_image_dir(self):
        self._image_mode = "dir"
        self._image_full_path = ""
        self._image_custom_files = []
        _set_path_field(self.image_dir_edit, "")
        self.image_dir_edit.setPlaceholderText("點擊選取圖像目錄")

    def _browse_vector_dir(self):
        start = self._vector_full_path if self._vector_mode == "dir" else ""
        path = QFileDialog.getExistingDirectory(self, "選擇向量目錄", start)
        if path:
            self._vector_mode = "dir"
            self._vector_full_path = path
            self._vector_custom_files = []
            _set_path_field(self.vector_dir_edit, path)
            self.vector_dir_edit.setPlaceholderText("點擊選取向量目錄")

    def _browse_vector_files(self):
        start = (
            str(Path(self._vector_custom_files[0]).parent)
            if self._vector_mode == "files" and self._vector_custom_files
            else ""
        )
        files, _ = QFileDialog.getOpenFileNames(
            self, "選取向量檔案", start,
            "向量檔案 (*.npz *.flo *.mat *.raw);;所有檔案 (*.*)"
        )
        if files:
            self._vector_mode = "files"
            self._vector_custom_files = list(files)
            self.vector_dir_edit.setReadOnly(False)
            self.vector_dir_edit.setText(f"{len(files)} 個檔案")
            self.vector_dir_edit.setReadOnly(True)

    def _clear_vector_dir(self):
        self._vector_mode = "dir"
        self._vector_full_path = ""
        self._vector_custom_files = []
        _set_path_field(self.vector_dir_edit, "")
        self.vector_dir_edit.setPlaceholderText("點擊選取向量目錄")

    # ── Card 2: 播放 ──────────────────────────────────────────────────

    def _build_playback_card(self) -> QWidget:
        card, layout = _card("播放")

        # Row 1 — 第幾對
        row1 = QHBoxLayout()
        row1.setSpacing(LABEL_GAP)

        row1.addWidget(QLabel("第幾對"))

        self._pair_edit = QLineEdit(str(self.viewer_settings.get("current_pair", 1)))
        self._pair_edit.setFixedSize(RANGE_EDIT_W, _FIELD_H)
        self._pair_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pair_edit.setValidator(QIntValidator(1, 99999, self))
        self._pair_edit.setProperty("variant", "range")
        self._pair_edit.editingFinished.connect(self._on_pair_edit_finished)
        row1.addWidget(self._pair_edit)

        self._total_label = QLabel("/ 0")
        self._total_label.setProperty("variant", "hint")
        row1.addWidget(self._total_label)

        row1.addStretch()

        layout.addLayout(row1)

        # Row 2 — 播放控制 + slider
        row2 = QHBoxLayout()
        row2.setSpacing(LABEL_GAP)

        _NAV_BTN_W = 34

        self.btn_prev = QPushButton("❮❮")
        self.btn_prev.setFixedSize(_NAV_BTN_W, _FIELD_H)
        self.btn_prev.setProperty("variant", "nav")
        self.btn_prev.clicked.connect(lambda: self._navigate(-1))
        row2.addWidget(self.btn_prev)

        self.btn_play = QPushButton()
        self.btn_play.setIcon(QIcon(_ICON_PLAY))
        self.btn_play.setIconSize(_PLAY_ICON_SIZE)
        self.btn_play.setFixedSize(_NAV_BTN_W, _FIELD_H)
        self.btn_play.setProperty("variant", "nav")
        self.btn_play.clicked.connect(self._on_play_clicked)
        row2.addWidget(self.btn_play)

        self.btn_next = QPushButton("❯❯")
        self.btn_next.setFixedSize(_NAV_BTN_W, _FIELD_H)
        self.btn_next.setProperty("variant", "nav")
        self.btn_next.clicked.connect(lambda: self._navigate(+1))
        row2.addWidget(self.btn_next)

        self._idx_slider = QSlider(Qt.Orientation.Horizontal)
        self._idx_slider.setRange(1, 1)
        self._idx_slider.setValue(1)
        self._idx_slider.setStyleSheet("QSlider { background: transparent; }")
        self._idx_slider.valueChanged.connect(self._on_slider_changed)
        row2.addWidget(self._idx_slider, stretch=1)

        layout.addLayout(row2)

        return card

    # ── Card 3: 繪圖模式 ───────────────────────────────────────────────

    def _build_plot_mode_card(self) -> QWidget:
        card, layout = _card("繪圖模式")

        # Top row — display mode segmented buttons (影像 / 向量 / 渦度)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(2)

        self._display_mode_group = QButtonGroup(self)
        self._display_mode_group.setExclusive(True)
        self._display_mode_btns: Dict[str, QPushButton] = {}
        for mode in ("影像", "向量", "渦度"):
            btn = QPushButton(mode)
            btn.setFixedHeight(_PLOT_MODE_BTN_H)
            btn.setCheckable(True)
            btn.setProperty("segmented", "true")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked, m=mode: self._on_display_mode_clicked(m))
            self._display_mode_group.addButton(btn)
            mode_row.addWidget(btn)
            self._display_mode_btns[mode] = btn

        # 流線 button (independent of display mode group)
        self._btn_streamline = QPushButton("流線")
        self._btn_streamline.setFixedHeight(_PLOT_MODE_BTN_H)
        self._btn_streamline.setCheckable(True)
        self._btn_streamline.setProperty("segmented", "true")
        self._btn_streamline.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_streamline.setEnabled(True)
        self._btn_streamline.clicked.connect(self._on_streamline_toggled)
        self._btn_streamline.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self._btn_streamline.customContextMenuRequested.connect(
            self._show_streamline_menu
        )
        self._streamlines_hidden = False
        mode_row.addSpacing(8)
        mode_row.addWidget(self._btn_streamline)

        mode_row.addStretch()
        layout.addLayout(mode_row)

        # Stacked content — per-mode options
        self._mode_stack = QStackedWidget()
        self._image_opts = self._build_image_opts()
        self._vector_opts = self._build_vector_opts()
        self._vort_opts = self._build_vorticity_opts()
        self._mode_stack.addWidget(self._image_opts)   # 0 → 影像
        self._mode_stack.addWidget(self._vector_opts)  # 1 → 向量
        self._mode_stack.addWidget(self._vort_opts)    # 2 → 渦度
        layout.addWidget(self._mode_stack)

        # Restore display mode
        cur_mode = self.viewer_settings.get("display_mode", "向量")
        self._set_display_mode(cur_mode)

        return card

    # ── 繪圖模式 → 影像 options ────────────────────────────────────────

    def _build_image_opts(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 4, 0, 0)
        lay.setSpacing(ROW_SPACING)
        hint = QLabel("(影像模式無額外繪圖選項)")
        hint.setProperty("variant", "hint")
        lay.addWidget(hint)
        return w

    # ── 繪圖模式 → 向量 options ────────────────────────────────────────

    def _build_vector_opts(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(ROW_SPACING)

        # Color mode toggle row — segmented 單色/多色 + 色盤 combo
        mode_row = QHBoxLayout()
        mode_row.setSpacing(LABEL_GAP)

        self._color_mode_group = QButtonGroup(self)
        self._color_mode_group.setExclusive(True)

        self._btn_single = QPushButton("單色")
        self._btn_single.setFixedHeight(_FIELD_H)
        self._btn_single.setCheckable(True)
        self._btn_single.setProperty("segmented", "true")
        self._btn_single.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_multi = QPushButton("多色")
        self._btn_multi.setFixedHeight(_FIELD_H)
        self._btn_multi.setCheckable(True)
        self._btn_multi.setProperty("segmented", "true")
        self._btn_multi.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_mode_group.addButton(self._btn_single)
        self._color_mode_group.addButton(self._btn_multi)
        self._btn_single.clicked.connect(lambda: self._on_color_mode_toggled("single"))
        self._btn_multi.clicked.connect(lambda: self._on_color_mode_toggled("multi"))
        mode_row.addWidget(self._btn_single)
        mode_row.addWidget(self._btn_multi)

        _lbl = QLabel("色盤:")
        mode_row.addWidget(_lbl)

        self._color_combo = CenteredComboBox()
        self._color_combo.setFixedSize(INPUT_MD, _FIELD_H)
        self._color_combo.setStyleSheet(COMBO_QSS)
        self._color_combo.currentTextChanged.connect(lambda _: self._safe_redraw())
        mode_row.addWidget(self._color_combo)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # Colorbar range row (shown only in multi-colour mode)
        self._cb_range_widget = QWidget()
        self._cb_range_widget.setMaximumHeight(_FIELD_H)
        self._cb_range_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        cb_range_layout = QHBoxLayout(self._cb_range_widget)
        cb_range_layout.setContentsMargins(0, 0, 0, 0)
        cb_range_layout.setSpacing(LABEL_GAP)

        self._cb_auto_btn = QPushButton("AUTO")
        self._cb_auto_btn.setFixedHeight(_FIELD_H - 2)
        self._cb_auto_btn.setCheckable(True)
        self._cb_auto_btn.setProperty("segmented", "true")
        self._cb_auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cb_auto_btn.clicked.connect(self._on_colorbar_auto_toggle)
        cb_range_layout.addWidget(self._cb_auto_btn)

        self._cb_manual_widget = QWidget()
        self._cb_manual_widget.setMaximumHeight(_FIELD_H)
        self._cb_manual_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        cb_man_layout = QHBoxLayout(self._cb_manual_widget)
        cb_man_layout.setContentsMargins(0, 0, 0, 0)
        cb_man_layout.setSpacing(LABEL_GAP)
        cb_man_layout.addWidget(QLabel("Min"))
        self._cb_min_edit = QLineEdit(str(self.viewer_settings.get("colorbar_min", 0.0)))
        self._cb_min_edit.setFixedSize(RANGE_EDIT_W, _FIELD_H - 2)
        self._cb_min_edit.setValidator(QDoubleValidator())
        self._cb_min_edit.setProperty("variant", "range")
        self._cb_min_edit.editingFinished.connect(lambda: self._safe_redraw())
        cb_man_layout.addWidget(self._cb_min_edit)
        cb_man_layout.addWidget(QLabel("Max"))
        self._cb_max_edit = QLineEdit(str(self.viewer_settings.get("colorbar_max", 10.0)))
        self._cb_max_edit.setFixedSize(RANGE_EDIT_W, _FIELD_H - 2)
        self._cb_max_edit.setValidator(QDoubleValidator())
        self._cb_max_edit.setProperty("variant", "range")
        self._cb_max_edit.editingFinished.connect(lambda: self._safe_redraw())
        cb_man_layout.addWidget(self._cb_max_edit)
        cb_range_layout.addWidget(self._cb_manual_widget)
        cb_range_layout.addStretch()
        layout.addWidget(self._cb_range_widget)

        # Grid skip
        self.slider_skip = QSlider(Qt.Orientation.Horizontal)
        self.slider_skip.setRange(1, 8)
        self.slider_skip.setFixedWidth(SLIDER_W)
        self.slider_skip.setStyleSheet("QSlider { background: transparent; }")
        self.spin_skip = QSpinBox()
        self.spin_skip.setRange(1, 8)
        self.spin_skip.setFixedSize(INPUT_SM, _FIELD_H)
        self.spin_skip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_skip.setStyleSheet(SPIN_QSS)
        cur_skip = int(self.viewer_settings.get("grid_skip", 1))
        self.slider_skip.setValue(cur_skip)
        self.spin_skip.setValue(cur_skip)
        self.slider_skip.valueChanged.connect(self.spin_skip.setValue)
        self.spin_skip.valueChanged.connect(self.slider_skip.setValue)
        self.slider_skip.valueChanged.connect(lambda _: self._safe_redraw())
        layout.addLayout(form_row("間隔大小", self.slider_skip, _VEC_LABEL_W,
                                  extra_widgets=[self.spin_skip]))

        # Quiver factor
        self.slider_scale = QSlider(Qt.Orientation.Horizontal)
        self.slider_scale.setRange(0, 60)   # ×0.5 → 0~30
        self.slider_scale.setFixedWidth(SLIDER_W)
        self.slider_scale.setStyleSheet("QSlider { background: transparent; }")
        self.spin_scale = QDoubleSpinBox()
        self.spin_scale.setRange(0.0, 30.0)
        self.spin_scale.setSingleStep(0.5)
        self.spin_scale.setDecimals(1)
        self.spin_scale.setFixedSize(INPUT_SM, _FIELD_H)
        self.spin_scale.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_scale.setStyleSheet(SPIN_QSS)
        cur_scale = min(float(self.viewer_settings.get("quiver_factor", 5.0)), 30.0)
        self.slider_scale.setValue(int(cur_scale * 2))
        self.spin_scale.setValue(cur_scale)
        self.slider_scale.valueChanged.connect(lambda v: self.spin_scale.setValue(v / 2.0))
        self.spin_scale.valueChanged.connect(lambda v: self.slider_scale.setValue(int(v * 2)))
        self.spin_scale.valueChanged.connect(lambda _: self._safe_redraw())
        layout.addLayout(form_row("向量縮放", self.slider_scale, _VEC_LABEL_W,
                                  extra_widgets=[self.spin_scale]))

        # Restore color mode + combo
        cur_enabled = self.viewer_settings.get("colorbar_enabled", False)
        self._colorbar_mode = "multi" if cur_enabled else "single"
        self._apply_color_mode()

        return w

    # ── 繪圖模式 → 渦度 options ────────────────────────────────────────

    def _build_vorticity_opts(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(ROW_SPACING)

        # Method dropdown
        self._method_combo = CenteredComboBox()
        self._method_combo.addItems(_VORT_METHODS)
        self._method_combo.setStyleSheet(COMBO_QSS)
        self._method_combo.setFixedSize(INPUT_LG, _FIELD_H)
        cur_method = self.viewer_settings.get("vorticity_method", "Central Difference")
        idx = self._method_combo.findText(cur_method)
        if idx >= 0:
            self._method_combo.setCurrentIndex(idx)
        self._method_combo.currentTextChanged.connect(lambda _: self._safe_redraw())
        layout.addLayout(form_row("方法", self._method_combo, _VORT_LABEL_W))

        # Colormap dropdown
        self._vort_cmap_combo = CenteredComboBox()
        self._vort_cmap_combo.addItems(_VORT_COLORMAP_OPTIONS)
        self._vort_cmap_combo.setStyleSheet(COMBO_QSS)
        self._vort_cmap_combo.setFixedSize(INPUT_LG, _FIELD_H)
        cur_cmap = self.viewer_settings.get("vort_cmap", "seismic")
        idx = self._vort_cmap_combo.findText(cur_cmap)
        if idx >= 0:
            self._vort_cmap_combo.setCurrentIndex(idx)
        self._vort_cmap_combo.currentTextChanged.connect(lambda _: self._safe_redraw())
        layout.addLayout(form_row("色盤", self._vort_cmap_combo, _VORT_LABEL_W))

        # Colorbar range (Auto + Min/Max — always visible, Min/Max disabled when Auto)
        vort_range_row = QHBoxLayout()
        vort_range_row.setSpacing(LABEL_GAP)

        self._vort_auto_btn = QPushButton("AUTO")
        self._vort_auto_btn.setFixedHeight(_FIELD_H - 2)
        self._vort_auto_btn.setCheckable(True)
        self._vort_auto_btn.setProperty("segmented", "true")
        self._vort_auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._vort_auto_btn.clicked.connect(self._on_vort_auto_toggle)
        vort_range_row.addWidget(self._vort_auto_btn)

        self._vort_manual_widget = QWidget()
        self._vort_manual_widget.setMaximumHeight(_FIELD_H)
        self._vort_manual_widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        vort_man_layout = QHBoxLayout(self._vort_manual_widget)
        vort_man_layout.setContentsMargins(0, 0, 0, 0)
        vort_man_layout.setSpacing(LABEL_GAP)
        vort_man_layout.addWidget(QLabel("Min"))
        self._vort_min_edit = QLineEdit(str(self.viewer_settings.get("vort_colorbar_min", -5.0)))
        self._vort_min_edit.setFixedSize(RANGE_EDIT_W, _FIELD_H - 2)
        self._vort_min_edit.setValidator(QDoubleValidator())
        self._vort_min_edit.setProperty("variant", "range")
        self._vort_min_edit.editingFinished.connect(lambda: self._safe_redraw())
        vort_man_layout.addWidget(self._vort_min_edit)
        vort_man_layout.addWidget(QLabel("Max"))
        self._vort_max_edit = QLineEdit(str(self.viewer_settings.get("vort_colorbar_max", 5.0)))
        self._vort_max_edit.setFixedSize(RANGE_EDIT_W, _FIELD_H - 2)
        self._vort_max_edit.setValidator(QDoubleValidator())
        self._vort_max_edit.setProperty("variant", "range")
        self._vort_max_edit.editingFinished.connect(lambda: self._safe_redraw())
        vort_man_layout.addWidget(self._vort_max_edit)
        vort_range_row.addWidget(self._vort_manual_widget)
        vort_range_row.addStretch()
        layout.addLayout(vort_range_row)

        # Restore auto/manual state
        cur_range_mode = self.viewer_settings.get("vort_colorbar_range_mode", "Auto")
        self._vort_is_auto = (cur_range_mode == "Auto")
        self._update_vort_auto_ui()

        return w

    # ------------------------------------------------------------------
    # Color mode helpers
    # ------------------------------------------------------------------

    def _apply_color_mode(self):
        is_multi = (self._colorbar_mode == "multi")
        # Update combo items
        self._color_combo.blockSignals(True)
        self._color_combo.clear()
        if is_multi:
            self._color_combo.addItems(_COLORMAP_OPTIONS)
            cur = self.viewer_settings.get("colorbar_cmap", "turbo")
        else:
            self._color_combo.addItems(_VECTOR_COLORS)
            cur = self.viewer_settings.get("vector_color", "lime")
        idx = self._color_combo.findText(cur)
        if idx >= 0:
            self._color_combo.setCurrentIndex(idx)
        self._color_combo.blockSignals(False)
        # Always show colorbar range row; disable when not in multi-colour mode
        self._cb_range_widget.setEnabled(is_multi)
        # Segmented button checked-state (QSS :checked handles the visual)
        self._btn_single.setChecked(not is_multi)
        self._btn_multi.setChecked(is_multi)
        # Colorbar Auto/Manual state
        cur_mode = self.viewer_settings.get("colorbar_range_mode", "Auto")
        self._cb_is_auto = (cur_mode == "Auto")
        self._update_colorbar_auto_ui()

    def _on_color_mode_toggled(self, mode: str):
        if self._colorbar_mode == mode:
            return
        self._colorbar_mode = mode
        self._apply_color_mode()
        self._safe_redraw()

    # -- Colorbar auto/manual ──────────────────────────────────────────

    def _on_colorbar_auto_toggle(self, checked: bool = None):
        if checked is not None:
            self._cb_is_auto = checked
        else:
            self._cb_is_auto = not self._cb_is_auto
        self._update_colorbar_auto_ui()
        self._safe_redraw()

    def _update_colorbar_auto_ui(self):
        self._cb_auto_btn.setChecked(self._cb_is_auto)
        self._cb_manual_widget.setEnabled(not self._cb_is_auto)

    def _on_vort_auto_toggle(self, checked: bool = None):
        if checked is not None:
            self._vort_is_auto = checked
        else:
            self._vort_is_auto = not self._vort_is_auto
        self._update_vort_auto_ui()
        self._safe_redraw()

    def _update_vort_auto_ui(self):
        self._vort_auto_btn.setChecked(self._vort_is_auto)
        self._vort_manual_widget.setEnabled(not self._vort_is_auto)

    # ------------------------------------------------------------------
    # Display mode helpers
    # ------------------------------------------------------------------

    def _set_display_mode(self, mode: str):
        self._current_display_mode = mode
        for m, btn in self._display_mode_btns.items():
            btn.setChecked(m == mode)
        idx = {"影像": 0, "向量": 1, "渦度": 2}.get(mode, 1)
        if hasattr(self, "_mode_stack"):
            self._mode_stack.setCurrentIndex(idx)
        if hasattr(self, "_btn_streamline"):
            self._btn_streamline.setEnabled(True)

    def _on_display_mode_clicked(self, mode: str):
        if getattr(self, "_current_display_mode", None) == mode:
            return
        self._set_display_mode(mode)
        self.plot_requested.emit()

    # ------------------------------------------------------------------
    # Playback helpers
    # ------------------------------------------------------------------

    def clear_view(self):
        self.update_pair_count(0)
        self._pair_edit.setText("1")

    def _on_play_clicked(self):
        self._is_playing = not self._is_playing
        self.btn_play.setIcon(QIcon(_ICON_PAUSE if self._is_playing else _ICON_PLAY))
        self.play_toggled.emit(self._is_playing)

    def _navigate(self, delta: int):
        if self._total_pairs == 0:
            return
        cur = self.get_current_pair()
        new_val = cur + delta
        if new_val < 1:
            new_val = self._total_pairs
        elif new_val > self._total_pairs:
            new_val = 1
        self.set_current_pair(new_val)
        self.plot_requested.emit()

    def _on_pair_edit_finished(self):
        try:
            val = int(self._pair_edit.text())
        except ValueError:
            val = 1
        val = max(1, min(val, max(1, self._total_pairs)))
        self.set_current_pair(val)
        self.plot_requested.emit()

    def _on_slider_changed(self, val: int):
        self._pair_edit.blockSignals(True)
        self._pair_edit.setText(str(val))
        self._pair_edit.blockSignals(False)
        self.plot_requested.emit()

    def _safe_redraw(self):
        self._redraw_timer.start()

    # ------------------------------------------------------------------
    # Streamline helpers
    # ------------------------------------------------------------------

    def _on_streamline_toggled(self, checked: bool):
        self.streamline_toggled.emit(checked)

    def _show_streamline_menu(self, pos):
        from PySide6.QtWidgets import QMenu, QColorDialog, QInputDialog

        menu = QMenu(self._btn_streamline)
        label = "顯示流線" if self._streamlines_hidden else "隱藏流線"
        act_hide = menu.addAction(label)
        act_delete = menu.addAction("刪除流線")
        menu.addSeparator()
        act_color = menu.addAction("流線顏色…")
        act_count = menu.addAction("拖曳釋放點數量…")
        action = menu.exec(self._btn_streamline.mapToGlobal(pos))
        if action == act_hide:
            self._streamlines_hidden = not self._streamlines_hidden
            self.streamline_visibility.emit(not self._streamlines_hidden)
        elif action == act_delete:
            self._streamlines_hidden = False
            self._btn_streamline.setChecked(False)
            self.streamline_clear.emit()
        elif action == act_color:
            from PySide6.QtGui import QColor
            initial = QColor(getattr(self, "_streamline_color", "#FFFFFF"))
            color = QColorDialog.getColor(initial, self, "流線顏色")
            if color.isValid():
                self._streamline_color = color.name()
                self.streamline_color_changed.emit(color.name())
        elif action == act_count:
            current = getattr(self, "_streamline_line_count", 10)
            val, ok = QInputDialog.getInt(
                self, "拖曳釋放點數量",
                "兩點連線上的釋放點個數:", current, 2, 100,
            )
            if ok:
                self._streamline_line_count = val
                self.streamline_count_changed.emit(val)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def update_pair_count(self, total: int):
        """Called by app.py after a scan to update slider range and total label."""
        self._total_pairs = total
        self._total_label.setText(f"/ {total}")
        if total > 0:
            self._idx_slider.setRange(1, total)
            cur = min(self.get_current_pair(), total)
            self.set_current_pair(cur)
        else:
            self._idx_slider.setRange(1, 1)
            self.set_current_pair(1)

    def get_current_pair(self) -> int:
        try:
            return int(self._pair_edit.text())
        except ValueError:
            return 1

    def set_current_pair(self, n: int):
        self._pair_edit.blockSignals(True)
        self._idx_slider.blockSignals(True)
        self._pair_edit.setText(str(n))
        self._idx_slider.setValue(n)
        self._pair_edit.blockSignals(False)
        self._idx_slider.blockSignals(False)

    def stop_playback(self):
        if self._is_playing:
            self._is_playing = False
            self.btn_play.setText("▶")
            self.play_toggled.emit(False)

    def deactivate_streamline(self):
        self._btn_streamline.setChecked(False)

    def get_values(self) -> Dict[str, Any]:
        """Return current viewer settings as a flat dict."""
        is_multi = (self._colorbar_mode == "multi")
        vort_method = self._method_combo.currentText() or "Central Difference"

        return {
            "image_dir": self._image_full_path if self._image_mode == "dir" else "",
            "image_custom_enabled": self._image_mode == "files",
            "image_custom_files": list(self._image_custom_files),
            "vector_dir": self._vector_full_path if self._vector_mode == "dir" else "",
            "vector_custom_enabled": self._vector_mode == "files",
            "vector_custom_files": list(self._vector_custom_files),
            "current_pair": self.get_current_pair(),
            "display_mode": getattr(self, "_current_display_mode", "向量"),
            "vector_color": (
                self._color_combo.currentText() if not is_multi
                else self.viewer_settings.get("vector_color", "lime")
            ),
            "grid_skip": self.spin_skip.value(),
            "quiver_factor": self.spin_scale.value(),
            "colorbar_enabled": is_multi,
            "colorbar_cmap": (
                self._color_combo.currentText() if is_multi
                else self.viewer_settings.get("colorbar_cmap", "turbo")
            ),
            "colorbar_range_mode": "Auto" if getattr(self, "_cb_is_auto", True) else "Manual",
            "colorbar_min": self._safe_float(self._cb_min_edit.text(), 0.0),
            "colorbar_max": self._safe_float(self._cb_max_edit.text(), 10.0),
            "vorticity_method": vort_method,
            "vort_cmap": self._vort_cmap_combo.currentText(),
            "vort_colorbar_range_mode": "Auto" if getattr(self, "_vort_is_auto", True) else "Manual",
            "vort_colorbar_min": self._safe_float(self._vort_min_edit.text(), -5.0),
            "vort_colorbar_max": self._safe_float(self._vort_max_edit.text(), 5.0),
        }

    def set_values(self, values: Dict[str, Any]) -> None:
        """Restore viewer settings (called on startup)."""
        # Image path / files
        if values.get("image_custom_enabled") and values.get("image_custom_files"):
            self._image_mode = "files"
            self._image_custom_files = list(values["image_custom_files"])
            count = len(self._image_custom_files)
            self.image_dir_edit.setReadOnly(False)
            self.image_dir_edit.setText(f"{count} 個檔案" if count else "")
            self.image_dir_edit.setReadOnly(True)
        elif "image_dir" in values:
            self._image_mode = "dir"
            self._image_full_path = values["image_dir"] or ""
            self._image_custom_files = []
            _set_path_field(self.image_dir_edit, self._image_full_path)
        # Vector path / files
        if values.get("vector_custom_enabled") and values.get("vector_custom_files"):
            self._vector_mode = "files"
            self._vector_custom_files = list(values["vector_custom_files"])
            count = len(self._vector_custom_files)
            self.vector_dir_edit.setReadOnly(False)
            self.vector_dir_edit.setText(f"{count} 個檔案" if count else "")
            self.vector_dir_edit.setReadOnly(True)
        elif "vector_dir" in values:
            self._vector_mode = "dir"
            self._vector_full_path = values["vector_dir"] or ""
            self._vector_custom_files = []
            _set_path_field(self.vector_dir_edit, self._vector_full_path)
        if "current_pair" in values:
            self.set_current_pair(int(values["current_pair"]))
        if "display_mode" in values:
            self._set_display_mode(values["display_mode"])
        if "colorbar_enabled" in values:
            self._colorbar_mode = "multi" if values["colorbar_enabled"] else "single"
        if "vector_color" in values:
            self.viewer_settings["vector_color"] = values["vector_color"]
        if "colorbar_cmap" in values:
            self.viewer_settings["colorbar_cmap"] = values["colorbar_cmap"]
        if "colorbar_range_mode" in values:
            self.viewer_settings["colorbar_range_mode"] = values["colorbar_range_mode"]
        if "colorbar_min" in values:
            self._cb_min_edit.setText(str(values["colorbar_min"]))
        if "colorbar_max" in values:
            self._cb_max_edit.setText(str(values["colorbar_max"]))
        if "grid_skip" in values:
            self.spin_skip.setValue(int(values["grid_skip"]))
        if "quiver_factor" in values:
            self.spin_scale.setValue(float(values["quiver_factor"]))
        if "vorticity_method" in values:
            idx = self._method_combo.findText(values["vorticity_method"])
            if idx >= 0:
                self._method_combo.setCurrentIndex(idx)
        if "vort_cmap" in values:
            idx = self._vort_cmap_combo.findText(values["vort_cmap"])
            if idx >= 0:
                self._vort_cmap_combo.setCurrentIndex(idx)
        if "vort_colorbar_range_mode" in values:
            self._vort_is_auto = (values["vort_colorbar_range_mode"] == "Auto")
            self._update_vort_auto_ui()
        if "vort_colorbar_min" in values:
            self._vort_min_edit.setText(str(values["vort_colorbar_min"]))
        if "vort_colorbar_max" in values:
            self._vort_max_edit.setText(str(values["vort_colorbar_max"]))
        # Reapply color mode to refresh combo
        self._apply_color_mode()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_float(text: str, default: float) -> float:
        try:
            return float(text)
        except (ValueError, TypeError):
            return default
