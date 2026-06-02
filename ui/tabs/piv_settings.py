from typing import Dict, Any, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QDoubleSpinBox, QSpinBox, QCheckBox
)
from PySide6.QtCore import Qt

from .._card_helper import _card
from ..widgets import CenteredComboBox, COMBO_QSS, SPIN_QSS, form_row
from ..tokens import (
    FIELD_H,
    INPUT_MD,
    CARD_SPACING,
    OUTER_MARGIN,
    ROW_SPACING,
    LABEL_GAP,
)


INT_AREA_OPTIONS = ["none", "8", "16", "32", "64", "128", "256", "512"]

_FILTER_PARAMS = [
    ("標準差過濾", "thres_std",    "建議 2~3"),
    ("中值過濾",   "thres_median", "建議 2~3"),
    ("全域過濾",   "thres_global", "一般非必要"),
]

# Label column widths (per-card)
_ANALYSIS_LABEL_W = 64   # 峰值擬合/窗格變形/重疊比例
_POSTPROC_LABEL_W = 90   # 標準差過濾/中值過濾/全域過濾/插值方法/權重平滑 (5 chinese chars)


class PivSettingsTab(QWidget):
    """PIV 設定頁籤（含後處理）"""

    def __init__(self, settings: Dict[str, Any], postproc_settings: Dict[str, Any]):
        super().__init__()
        self.settings = settings
        self.postproc_settings = postproc_settings
        self._thres_spins: Dict[str, Tuple[QCheckBox, QDoubleSpinBox]] = {}
        self._create_widgets()

    def _create_widgets(self):
        font = self.font()
        font.setPixelSize(12)
        self.setFont(font)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(*OUTER_MARGIN)
        outer.setSpacing(CARD_SPACING)

        outer.addWidget(self._build_int_area_card())
        outer.addWidget(self._build_analysis_params_card())
        outer.addWidget(self._build_postproc_card())
        outer.addWidget(self._build_advanced_card())
        outer.addStretch()

    # ------------------------------------------------------------------
    # Cards
    # ------------------------------------------------------------------

    def _build_int_area_card(self) -> QWidget:
        card, layout = _card("質問窗")

        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(ROW_SPACING)

        int_area_keys = [
            ("Int Area 1", "int_area_1"), ("Int Area 2", "int_area_2"),
            ("Int Area 3", "int_area_3"), ("Int Area 4", "int_area_4"),
            ("Int Area 5", "int_area_5"), ("Int Area 6", "int_area_6"),
        ]

        self._combo_int_areas: Dict[str, CenteredComboBox] = {}

        for idx, (label, key) in enumerate(int_area_keys):
            row, col = idx // 2, (idx % 2) * 2
            grid.addWidget(QLabel(label), row, col, Qt.AlignmentFlag.AlignLeft)
            combo = CenteredComboBox()
            combo.addItems(INT_AREA_OPTIONS)
            combo.setStyleSheet(COMBO_QSS)
            val = str(self.settings.get(key, "none"))
            i = combo.findText(val)
            if i >= 0:
                combo.setCurrentIndex(i)
            combo.setFixedSize(INPUT_MD, FIELD_H)
            grid.addWidget(combo, row, col + 1, Qt.AlignmentFlag.AlignLeft)
            self._combo_int_areas[key] = combo

        wrap = QHBoxLayout()
        wrap.addLayout(grid)
        wrap.addStretch()
        layout.addLayout(wrap)

        return card

    def _build_analysis_params_card(self) -> QWidget:
        card, layout = _card("分析參數")

        # ── 峰值擬合 ──────────────────────────────────────────────────
        self.combo_subpix = CenteredComboBox()
        self.combo_subpix.addItems(["3-pt Gauss", "2D Gauss"])
        self.combo_subpix.setStyleSheet(COMBO_QSS)
        val = "2D Gauss" if self.settings.get("sub_pix_method", 2) == 2 else "3-pt Gauss"
        self.combo_subpix.setCurrentText(val)
        self.combo_subpix.setFixedSize(INPUT_MD, FIELD_H)
        layout.addLayout(form_row("峰值擬合", self.combo_subpix, _ANALYSIS_LABEL_W))

        # ── 窗格變形 ──────────────────────────────────────────────────
        self.combo_wdeform = CenteredComboBox()
        self.combo_wdeform.addItems(["linear", "spline"])
        self.combo_wdeform.setStyleSheet(COMBO_QSS)
        self.combo_wdeform.setCurrentText(self.settings.get("window_deform", "linear"))
        self.combo_wdeform.setFixedSize(INPUT_MD, FIELD_H)
        layout.addLayout(form_row("窗格變形", self.combo_wdeform, _ANALYSIS_LABEL_W))

        # ── 重疊比例 ──────────────────────────────────────────────────
        self.spin_overlap = QSpinBox()
        self.spin_overlap.setRange(0, 90)
        self.spin_overlap.setSingleStep(10)
        self.spin_overlap.setSuffix("%")
        self.spin_overlap.setFixedSize(INPUT_MD, FIELD_H)
        self.spin_overlap.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spin_overlap.setStyleSheet(SPIN_QSS)
        overlap_val = round(self.settings.get("overlap", 0.5) * 100)
        self.spin_overlap.setValue(overlap_val)
        layout.addLayout(form_row("重疊比例", self.spin_overlap, _ANALYSIS_LABEL_W))

        return card

    def _build_postproc_card(self) -> QWidget:
        card, layout = _card("後處理")

        grid = QGridLayout()
        grid.setHorizontalSpacing(LABEL_GAP)
        grid.setVerticalSpacing(ROW_SPACING)
        grid.setColumnMinimumWidth(0, _POSTPROC_LABEL_W)

        # ── Filter rows ────────────────────────────────────────────────
        for row_idx, (label, key, hint) in enumerate(_FILTER_PARAMS):
            val = self.postproc_settings.get(key, -1.0)
            is_checked = (val != -1.0)
            display_val = val if is_checked else 5.0

            chk = QCheckBox(label)
            chk.setChecked(is_checked)

            spin = QDoubleSpinBox()
            spin.setRange(0.0, 100.0)
            spin.setDecimals(2)
            spin.setSingleStep(0.5)
            spin.setFixedSize(INPUT_MD, FIELD_H)
            spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spin.setStyleSheet(SPIN_QSS)
            spin.setValue(display_val)
            spin.setEnabled(is_checked)

            chk.toggled.connect(spin.setEnabled)

            lbl_hint = QLabel(hint)
            lbl_hint.setProperty("variant", "hint")

            grid.addWidget(chk,      row_idx, 0, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(spin,     row_idx, 1, Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(lbl_hint, row_idx, 2, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            self._thres_spins[key] = (chk, spin)

        # ── 插值方法 row ───────────────────────────────────────────────
        method_val = self.postproc_settings.get("interp_method", 2)
        interp_is_checked = (method_val != -1)

        self.chk_interp = QCheckBox("插值方法")
        self.chk_interp.setChecked(interp_is_checked)

        self.combo_interp = CenteredComboBox()
        self.combo_interp.addItems(["Linear", "Cubic Spline"])
        self.combo_interp.setFixedSize(INPUT_MD, FIELD_H)
        self.combo_interp.setStyleSheet(COMBO_QSS)
        self.combo_interp.setEnabled(interp_is_checked)

        if method_val == 1:
            self.combo_interp.setCurrentText("Linear")
        else:
            self.combo_interp.setCurrentText("Cubic Spline")

        self.chk_interp.toggled.connect(self.combo_interp.setEnabled)

        grid.addWidget(self.chk_interp, 3, 0, Qt.AlignmentFlag.AlignLeft)
        grid.addWidget(self.combo_interp, 3, 1, Qt.AlignmentFlag.AlignLeft)

        # ── 權重平滑 row ───────────────────────────────────────────────
        self.chk_smooth = QCheckBox("權重平滑")
        self.chk_smooth.setChecked(self.postproc_settings.get("smooth_data", True))
        grid.addWidget(self.chk_smooth, 4, 0, Qt.AlignmentFlag.AlignLeft)

        wrap = QHBoxLayout()
        wrap.addLayout(grid)
        wrap.addStretch()
        layout.addLayout(wrap)

        return card

    def _build_advanced_card(self) -> QWidget:
        card, layout = _card("其它選項")

        # Label column for these checkbox rows — align hint labels across
        # three rows so "針對低SNR影像" / "針對非連續光源" share left edge.
        adv_label_w = 120  # 重複4次CC分析 is 8 chars ≈ 96px, leave breathing room

        # ── 重複4次CC分析 ──────────────────────────────────────────────
        self.chk_repeat_corr = QCheckBox("重複4次CC分析")
        self.chk_repeat_corr.setChecked(self.settings.get("repeat_corr", False))
        self.chk_repeat_corr.setFixedWidth(adv_label_w)
        lbl_repeat_hint = QLabel("針對低SNR影像")
        lbl_repeat_hint.setProperty("variant", "hint")
        repeat_row = QHBoxLayout()
        repeat_row.setSpacing(LABEL_GAP)
        repeat_row.addWidget(self.chk_repeat_corr)
        repeat_row.addWidget(lbl_repeat_hint)
        repeat_row.addStretch()
        layout.addLayout(repeat_row)

        # ── 自相關分析 ─────────────────────────────────────────────────
        # disable_autocorr=True means autocorr is OFF; checkbox checked = autocorr ON
        self.chk_autocorr = QCheckBox("自相關分析")
        self.chk_autocorr.setChecked(not self.settings.get("disable_autocorr", True))
        self.chk_autocorr.setFixedWidth(adv_label_w)
        lbl_autocorr_hint = QLabel("針對非連續光源")
        lbl_autocorr_hint.setProperty("variant", "hint")
        autocorr_row = QHBoxLayout()
        autocorr_row.setSpacing(LABEL_GAP)
        autocorr_row.addWidget(self.chk_autocorr)
        autocorr_row.addWidget(lbl_autocorr_hint)
        autocorr_row.addStretch()
        layout.addLayout(autocorr_row)

        # ── 灰階反轉 ───────────────────────────────────────────────────
        self.chk_invert_gray = QCheckBox("灰階反轉")
        self.chk_invert_gray.setChecked(self.settings.get("invert_gray", False))
        layout.addWidget(self.chk_invert_gray)

        return card

    # ------------------------------------------------------------------
    # get_values / set_values
    # ------------------------------------------------------------------

    def get_values(self) -> Dict[str, Any]:
        subpix_map = {"3-pt Gauss": 1, "2D Gauss": 2}
        result: Dict[str, Any] = {
            "overlap": self.spin_overlap.value() / 100.0,
            "sub_pix_method": subpix_map.get(self.combo_subpix.currentText(), 2),
            "window_deform": self.combo_wdeform.currentText(),
            "repeat_corr": self.chk_repeat_corr.isChecked(),
            "disable_autocorr": not self.chk_autocorr.isChecked(),
            "invert_gray": self.chk_invert_gray.isChecked(),
        }
        for key, combo in self._combo_int_areas.items():
            result[key] = combo.currentText()
        return result

    def get_postproc_values(self) -> Dict[str, Any]:
        interp_map = {"Linear": 1, "Cubic Spline": 2}
        result: Dict[str, Any] = {
            "smooth_data": self.chk_smooth.isChecked(),
            "interp_method": (
                interp_map.get(self.combo_interp.currentText(), 2)
                if self.chk_interp.isChecked() else -1
            ),
        }
        for key, (chk, spin) in self._thres_spins.items():
            result[key] = spin.value() if chk.isChecked() else -1.0
        return result

    def set_values(self, values: Dict[str, Any]):
        for key, combo in self._combo_int_areas.items():
            if key in values:
                i = combo.findText(str(values[key]))
                if i >= 0:
                    combo.setCurrentIndex(i)
        if "overlap" in values:
            self.spin_overlap.setValue(round(float(values["overlap"]) * 100))
        if "sub_pix_method" in values:
            val = "2D Gauss" if values["sub_pix_method"] == 2 else "3-pt Gauss"
            self.combo_subpix.setCurrentText(val)
        if "window_deform" in values:
            self.combo_wdeform.setCurrentText(values["window_deform"])
        if "repeat_corr" in values:
            self.chk_repeat_corr.setChecked(values["repeat_corr"])
        if "disable_autocorr" in values:
            self.chk_autocorr.setChecked(not values["disable_autocorr"])
        if "invert_gray" in values:
            self.chk_invert_gray.setChecked(values["invert_gray"])

    def set_postproc_values(self, values: Dict[str, Any]):
        for key, (chk, spin) in self._thres_spins.items():
            if key in values:
                val = values[key]
                is_active = (val != -1.0)
                chk.setChecked(is_active)
                spin.setValue(val if is_active else 5.0)
        if "interp_method" in values:
            m = values["interp_method"]
            if m == -1:
                self.chk_interp.setChecked(False)
            else:
                self.chk_interp.setChecked(True)
                self.combo_interp.setCurrentText("Linear" if m == 1 else "Cubic Spline")
        if "smooth_data" in values:
            self.chk_smooth.setChecked(values["smooth_data"])
