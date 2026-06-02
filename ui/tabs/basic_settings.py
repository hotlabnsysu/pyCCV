import multiprocessing
from typing import Dict, Any

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox,
    QButtonGroup, QSlider, QSpinBox, QDoubleSpinBox,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal

from ..widgets import CenteredComboBox, COMBO_QSS, SPIN_QSS, form_row
from ..components.directory_picker import DirectoryPickerCard
from .._card_helper import _card
from ..tokens import (
    FIELD_H as _FIELD_H,
    INPUT_SM,
    INPUT_MD,
    SLIDER_W,
    CARD_MARGIN,
    OUTER_MARGIN,
    CARD_SPACING,
    ROW_SPACING,
    LABEL_GAP,
)

try:
    import psutil
    _PHYSICAL_CORES = psutil.cpu_count(logical=False) or (multiprocessing.cpu_count() // 2)
except Exception:
    _PHYSICAL_CORES = multiprocessing.cpu_count() // 2 or 1
_LOGICAL_CORES = multiprocessing.cpu_count()

# Label column width for 即時繪圖 / 輸出格式 rows (4 Chinese chars ≈ 56px + margin)
_PLOT_LABEL_W = 64



class BasicSettingsTab(QWidget):
    """基本設定頁籤"""

    plot_params_changed = Signal()
    paths_changed = Signal(dict)  # forwarded from DirectoryPickerCard

    def __init__(self, settings: Dict[str, Any]):
        super().__init__()
        self.settings = settings
        self.physical_cores = max(1, _PHYSICAL_CORES)
        self.logical_cores = max(1, _LOGICAL_CORES)
        self._dir_card: DirectoryPickerCard | None = None
        self._create_widgets()

    # ------------------------------------------------------------------
    # Widget creation
    # ------------------------------------------------------------------

    def _create_widgets(self):
        font = self.font()
        font.setPixelSize(12)
        self.setFont(font)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(*OUTER_MARGIN)
        outer.setSpacing(CARD_SPACING)

        outer.addWidget(self._build_dir_card())
        outer.addWidget(self._build_perf_card())
        outer.addWidget(self._build_output_card())
        outer.addWidget(self._build_plot_card())
        outer.addStretch()

    def _build_dir_card(self) -> QWidget:
        self._dir_card = DirectoryPickerCard(self.settings)
        # Keep legacy attribute aliases so existing get_values() still works
        self._dir_card.paths_changed.connect(self.paths_changed.emit)
        return self._dir_card

    def _build_perf_card(self) -> QWidget:
        card, layout = _card("運算資源")

        # ── CPU 平行 row ───────────────────────────────────────────────
        parallel_row = QHBoxLayout()
        parallel_row.setSpacing(LABEL_GAP)

        self.chk_parallel = QCheckBox("CPU 平行")
        cur_mode = self.settings.get("compute_mode", "cpu")
        self.chk_parallel.setChecked(cur_mode == "cpu_parallel")

        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(2, 12)
        self.spin_workers.setSingleStep(1)
        self.spin_workers.setFixedSize(INPUT_SM, _FIELD_H)
        self.spin_workers.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_workers.setStyleSheet(SPIN_QSS)

        cur_workers = self.settings.get("num_workers") or 4
        cur_workers = max(2, min(12, int(cur_workers)))
        if cur_workers > self.physical_cores:
            cur_workers = min(12, self.physical_cores)
        self.spin_workers.setValue(cur_workers)
        self.spin_workers.setEnabled(self.chk_parallel.isChecked())
        self.spin_workers.valueChanged.connect(self._on_worker_changed)
        self.chk_parallel.toggled.connect(self.spin_workers.setEnabled)

        lbl_perf_hint = QLabel("建議 4~6 核心")
        lbl_perf_hint.setProperty("variant", "hint")

        parallel_row.addWidget(self.chk_parallel)
        parallel_row.addWidget(self.spin_workers)
        parallel_row.addWidget(lbl_perf_hint)
        parallel_row.addStretch()
        layout.addLayout(parallel_row)

        # ── CPU info ───────────────────────────────────────────────────
        info_text = f"本機 CPU: {self.physical_cores} P-Cores / {self.logical_cores} Threads"
        lbl_cpu_info = QLabel(info_text)
        lbl_cpu_info.setProperty("variant", "hint")
        layout.addWidget(lbl_cpu_info)

        return card

    def _on_worker_changed(self, val: int):
        if val > self.physical_cores:
            max_allowed = min(12, self.physical_cores)
            QMessageBox.warning(
                self, "核心數超出本機配置",
                f"您選擇了 {val} 個核心，但系統偵測到本機只有 {self.physical_cores} 個實體核心。\n"
                f"建議不超載超執行緒，否則效能可能反而下降。系統已自動修正為 {max_allowed}。"
            )
            self.spin_workers.setValue(max_allowed)

    def _build_output_card(self) -> QWidget:
        card, layout = _card("輸出選項")

        chk_row = QHBoxLayout()
        chk_row.setSpacing(LABEL_GAP * 2)  # wider spacing between option checkboxes
        self.chk_smooth = QCheckBox("Smooth")
        self.chk_smooth.setChecked(self.settings.get("export_smooth", False))
        self.chk_interp = QCheckBox("Interp")
        self.chk_interp.setChecked(self.settings.get("export_interp", False))
        self.chk_filt = QCheckBox("Filter")
        self.chk_filt.setChecked(self.settings.get("export_filt", False))
        self.chk_raw = QCheckBox("Raw")
        self.chk_raw.setChecked(self.settings.get("export_raw", False))
        for chk in [self.chk_smooth, self.chk_interp, self.chk_filt, self.chk_raw]:
            chk_row.addWidget(chk)
        chk_row.addStretch()
        layout.addLayout(chk_row)

        self.combo_format = CenteredComboBox()
        self.combo_format.addItems(["npz", "raw", "mat", "flo"])
        self.combo_format.setStyleSheet(COMBO_QSS)
        cur_fmt = self.settings.get("output_format", "npz")
        idx = self.combo_format.findText(cur_fmt)
        if idx >= 0:
            self.combo_format.setCurrentIndex(idx)
        self.combo_format.setFixedSize(INPUT_SM, _FIELD_H)
        layout.addLayout(form_row("輸出格式", self.combo_format, _PLOT_LABEL_W))

        return card

    def _build_plot_card(self) -> QWidget:
        card, layout = _card("即時繪圖")

        # Segmented buttons for plot mode (mutually exclusive, visually distinct from checkboxes)
        mode_row = QHBoxLayout()
        mode_row.setSpacing(2)
        self._plot_mode_group = QButtonGroup(self)
        self._plot_mode_group.setExclusive(True)
        mode_labels = [(0, "不繪圖"), (1, "Raw"), (2, "Filter"), (3, "Smooth")]
        self._plot_buttons = {}
        for val, text in mode_labels:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setFixedHeight(_FIELD_H)
            btn.setProperty("segmented", "true")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._plot_mode_group.addButton(btn, val)
            mode_row.addWidget(btn)
            self._plot_buttons[val] = btn
        mode_row.addStretch()

        cur_mode = self.settings.get("plot_now", 3)
        if cur_mode in self._plot_buttons:
            self._plot_buttons[cur_mode].setChecked(True)
        else:
            self._plot_buttons[3].setChecked(True)

        self._plot_mode_group.idToggled.connect(
            lambda _id, checked: self.plot_params_changed.emit() if checked else None
        )
        layout.addLayout(mode_row)

        # Vector color
        self.combo_color = CenteredComboBox()
        self.combo_color.addItems(["lime", "red", "blue", "yellow", "cyan", "magenta", "white", "black"])
        self.combo_color.setStyleSheet(COMBO_QSS)
        cur_color = self.settings.get("vector_color", "lime")
        idx = self.combo_color.findText(cur_color)
        if idx >= 0:
            self.combo_color.setCurrentIndex(idx)
        self.combo_color.setFixedSize(INPUT_MD, _FIELD_H)
        self.combo_color.currentTextChanged.connect(lambda _: self.plot_params_changed.emit())
        layout.addLayout(form_row("向量顏色", self.combo_color, _PLOT_LABEL_W))

        # Grid skip
        self.slider_skip = QSlider(Qt.Orientation.Horizontal)
        self.slider_skip.setRange(1, 8)
        self.slider_skip.setSingleStep(1)
        self.slider_skip.setFixedWidth(SLIDER_W)
        self.slider_skip.setStyleSheet("QSlider { background: transparent; }")
        self.spin_skip = QSpinBox()
        self.spin_skip.setRange(1, 8)
        self.spin_skip.setFixedSize(INPUT_SM, _FIELD_H)
        self.spin_skip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_skip.setStyleSheet(SPIN_QSS)
        cur_skip = min(self.settings.get("grid_skip", 1), 8)
        self.slider_skip.setValue(cur_skip)
        self.spin_skip.setValue(cur_skip)
        self.slider_skip.valueChanged.connect(self.spin_skip.setValue)
        self.spin_skip.valueChanged.connect(self.slider_skip.setValue)
        self.slider_skip.valueChanged.connect(lambda _: self.plot_params_changed.emit())
        layout.addLayout(form_row("間隔大小", self.slider_skip, _PLOT_LABEL_W,
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
        cur_scale = min(float(self.settings.get("quiver_factor", 5.0)), 30.0)
        self.slider_scale.setValue(int(cur_scale * 2))
        self.spin_scale.setValue(cur_scale)
        self.slider_scale.valueChanged.connect(lambda v: self.spin_scale.setValue(v / 2.0))
        self.spin_scale.valueChanged.connect(lambda v: self.slider_scale.setValue(int(v * 2)))
        self.spin_scale.valueChanged.connect(lambda _: self.plot_params_changed.emit())
        layout.addLayout(form_row("向量縮放", self.slider_scale, _PLOT_LABEL_W,
                                  extra_widgets=[self.spin_scale]))

        return card

    # ------------------------------------------------------------------
    # get_values / set_values
    # ------------------------------------------------------------------

    def get_values(self) -> Dict[str, Any]:
        dir_vals = self._dir_card.get_values() if self._dir_card else {}
        return {
            **dir_vals,
            "compute_mode": "cpu_parallel" if self.chk_parallel.isChecked() else "cpu",
            "num_workers": self.spin_workers.value(),
            "export_smooth": self.chk_smooth.isChecked(),
            "export_interp": self.chk_interp.isChecked(),
            "export_filt": self.chk_filt.isChecked(),
            "export_raw": self.chk_raw.isChecked(),
            "output_format": self.combo_format.currentText(),
            "plot_now": self._plot_mode_group.checkedId(),
            "vector_color": self.combo_color.currentText(),
            "grid_skip": self.spin_skip.value(),
            "quiver_factor": self.spin_scale.value(),
        }

    def set_dir_values(self, values: Dict[str, Any]) -> None:
        """Update only the directory card fields (used for cross-tab sync)."""
        if self._dir_card:
            self._dir_card.set_values(values)

    def set_values(self, values: Dict[str, Any]):
        if self._dir_card:
            self._dir_card.set_values(values)
        if "compute_mode" in values:
            self.chk_parallel.setChecked(values["compute_mode"] == "cpu_parallel")
        if "num_workers" in values:
            try:
                v = max(2, min(12, int(values["num_workers"])))
                self.spin_workers.setValue(v)
            except (TypeError, ValueError):
                pass
        if "export_smooth" in values:
            self.chk_smooth.setChecked(values["export_smooth"])
        if "export_interp" in values:
            self.chk_interp.setChecked(values["export_interp"])
        if "export_filt" in values:
            self.chk_filt.setChecked(values["export_filt"])
        if "export_raw" in values:
            self.chk_raw.setChecked(values["export_raw"])
        if "output_format" in values:
            idx = self.combo_format.findText(values["output_format"])
            if idx >= 0:
                self.combo_format.setCurrentIndex(idx)
        if "plot_now" in values:
            mode = values["plot_now"]
            if mode in self._plot_buttons:
                self._plot_buttons[mode].setChecked(True)
        if "vector_color" in values:
            idx = self.combo_color.findText(values["vector_color"])
            if idx >= 0:
                self.combo_color.setCurrentIndex(idx)
        if "grid_skip" in values:
            self.spin_skip.setValue(int(values["grid_skip"]))
        if "quiver_factor" in values:
            self.spin_scale.setValue(float(values["quiver_factor"]))
