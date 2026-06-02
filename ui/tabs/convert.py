"""ConvertTab — SERVICE 頁籤

單張卡片 "檔案格式轉換" 包含：
    1. 輸入 / 輸出目錄選取 (視覺與功能同基本設定)
    2. 偵測結果顯示
    3. 輸出格式選擇
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from services.convert_service import (
    SUPPORTED_CONVERT_FORMATS,
    detect_formats,
    scan_files_list,
    scan_folder_recursive,
)
from ..widgets import (
    COMBO_QSS, CenteredComboBox,
    make_clear_btn as _make_clear_btn,
    style_path_field as _style_path_field,
    set_path_field as _set_path_field,
)
from .._card_helper import _card
from ..tokens import (
    FIELD_H as _FIELD_H,
    INPUT_SM,
    OUTER_MARGIN,
    CARD_SPACING,
    LABEL_GAP,
)

_DATA_FILE_FILTER = (
    "資料檔案 (*.npz *.flo *.mat *.raw);;"
    "NPZ (*.npz);;"
    "FLO (*.flo);;"
    "MAT (*.mat);;"
    "RAW (*.raw);;"
    "所有檔案 (*.*)"
)


class ConvertTab(QWidget):
    """SERVICE 頁籤 — 檔案格式轉換 (單卡片)"""

    def __init__(self, initial_values: Dict[str, Any] | None = None, parent: QWidget | None = None):
        super().__init__(parent)

        # Internal state
        self._input_mode: str = "none"   # "none" | "dir" | "files"
        self._custom_selected_files: List[str] = []
        self._task_list: List[Tuple[Path, Optional[str]]] = []
        self._input_full_path: str = ""
        self._output_full_path: str = ""

        self._create_widgets()
        if initial_values:
            self.set_values(initial_values)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _create_widgets(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(*OUTER_MARGIN)
        outer.setSpacing(CARD_SPACING)

        outer.addWidget(self._build_main_card())
        outer.addStretch()

    def _build_main_card(self) -> QWidget:
        card, layout = _card("檔案格式轉換")

        # ── 輸入 row (identical to DirectoryPickerCard) ─────────────────
        self.input_edit = QLineEdit("")
        _style_path_field(self.input_edit)
        self.input_edit.setPlaceholderText("點擊選取目錄")
        self.input_edit.mousePressEvent = lambda _e: self._browse_input()

        self._btn_input_files = QPushButton("選檔")
        self._btn_input_files.setFixedSize(38, _FIELD_H)
        self._btn_input_files.setToolTip("選取資料檔案 (可多選)")
        self._btn_input_files.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_input_files.setProperty("variant", "select")
        self._btn_input_files.clicked.connect(self._browse_input_files)

        self._btn_clear_input = _make_clear_btn()
        self._btn_clear_input.clicked.connect(self._clear_input)
        self.input_edit.textChanged.connect(
            lambda t: self._btn_clear_input.setVisible(bool(t))
        )

        in_row = QHBoxLayout()
        in_row.setSpacing(LABEL_GAP)
        in_row.addWidget(QLabel("輸入"), 0, Qt.AlignmentFlag.AlignVCenter)
        in_row.addWidget(self.input_edit, stretch=1)
        in_row.addWidget(self._btn_input_files, 0, Qt.AlignmentFlag.AlignVCenter)
        in_row.addWidget(self._btn_clear_input, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(in_row)

        # ── 輸出 row (identical to DirectoryPickerCard) ─────────────────
        self.output_edit = QLineEdit("")
        _style_path_field(self.output_edit)
        self.output_edit.setPlaceholderText("點擊選取輸出目錄")
        self.output_edit.mousePressEvent = lambda _e: self._browse_output()

        self._btn_clear_output = _make_clear_btn()
        self._btn_clear_output.clicked.connect(self._clear_output)
        self.output_edit.textChanged.connect(
            lambda t: self._btn_clear_output.setVisible(bool(t))
        )

        out_row = QHBoxLayout()
        out_row.setSpacing(LABEL_GAP)
        out_row.addWidget(QLabel("輸出"), 0, Qt.AlignmentFlag.AlignVCenter)
        out_row.addWidget(self.output_edit, stretch=1)
        out_row.addWidget(self._btn_clear_output, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(out_row)

        # ── 輸出格式 row ──────────────────────────────────────────────
        fmt_row = QHBoxLayout()
        fmt_row.setSpacing(LABEL_GAP)

        lbl_fmt = QLabel("輸出格式")
        fmt_row.addWidget(lbl_fmt, 0, Qt.AlignmentFlag.AlignVCenter)

        self._fmt_combo = CenteredComboBox()
        self._fmt_combo.addItems([f.upper() for f in SUPPORTED_CONVERT_FORMATS])
        self._fmt_combo.setFixedSize(INPUT_SM, _FIELD_H)
        self._fmt_combo.setStyleSheet(COMBO_QSS)
        fmt_row.addWidget(self._fmt_combo, 0, Qt.AlignmentFlag.AlignVCenter)
        fmt_row.addStretch()

        layout.addLayout(fmt_row)

        # ── 偵測結果 (在輸出格式下方) ─────────────────────────────────
        self._detect_label = QLabel("尚未選取來源")
        self._detect_label.setProperty("variant", "detect")
        self._detect_label.setWordWrap(True)
        layout.addWidget(self._detect_label)

        return card

    # ------------------------------------------------------------------
    # Helper: update detect label variant
    # ------------------------------------------------------------------
    def _set_detect_variant(self, variant: str) -> None:
        """variant: 'detect' | 'detect-ok' | 'detect-warn'"""
        self._detect_label.setProperty("variant", variant)
        self._detect_label.style().unpolish(self._detect_label)
        self._detect_label.style().polish(self._detect_label)

    # ------------------------------------------------------------------
    # Browse / clear (mirrors DirectoryPickerCard semantics)
    # ------------------------------------------------------------------

    def _browse_input(self) -> None:
        start = self._input_full_path if self._input_mode == "dir" else ""
        folder = QFileDialog.getExistingDirectory(
            self, "選擇輸入目錄", start
        )
        if folder:
            self._set_folder(Path(folder))

    def _browse_input_files(self) -> None:
        start = (
            str(Path(self._custom_selected_files[0]).parent)
            if self._input_mode == "files" and self._custom_selected_files
            else ""
        )
        paths, _ = QFileDialog.getOpenFileNames(
            self, "選取資料檔案", start, _DATA_FILE_FILTER
        )
        if paths:
            self._set_files([Path(p) for p in paths])

    def _browse_output(self) -> None:
        start = self._output_full_path or ""
        folder = QFileDialog.getExistingDirectory(
            self, "選擇輸出目錄", start
        )
        if folder:
            self._output_full_path = folder
            _set_path_field(self.output_edit, folder)

    def _clear_input(self) -> None:
        self._input_mode = "none"
        self._input_full_path = ""
        self._custom_selected_files = []
        self._task_list = []

        _set_path_field(self.input_edit, "")
        self.input_edit.setPlaceholderText("點擊選取目錄")
        self._detect_label.setText("尚未選取來源")
        self._set_detect_variant("detect")

    def _clear_output(self) -> None:
        self._output_full_path = ""
        _set_path_field(self.output_edit, "")

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _set_files(self, paths: List[Path]) -> None:
        valid, count = scan_files_list([str(p) for p in paths])
        if not valid:
            self._detect_label.setText("所選檔案無支援格式")
            self._set_detect_variant("detect-warn")
            return

        self._input_mode = "files"
        self._custom_selected_files = [str(p) for p in valid]
        self._task_list = [(p, None) for p in valid]

        self.input_edit.setReadOnly(False)
        self.input_edit.setText(
            f"{count} 個檔案" if count > 1 else str(valid[0])
        )
        self.input_edit.setReadOnly(True)

        fmts = detect_formats(valid)
        fmt_str = ", ".join(f.upper() for f in sorted(fmts))
        self._detect_label.setText(
            f"已選取 {count} 個檔案，格式: {fmt_str}"
        )
        self._set_detect_variant("detect-ok")

    def _set_folder(self, folder: Path) -> None:
        self._input_full_path = str(folder)
        _set_path_field(self.input_edit, str(folder))
        self._detect_label.setText("掃描中...")
        self._set_detect_variant("detect")

        try:
            structure, total, folders = scan_folder_recursive(folder)
        except Exception as exc:
            self._detect_label.setText(f"掃描失敗: {exc}")
            self._set_detect_variant("detect-warn")
            return

        self._input_mode = "dir"
        self._custom_selected_files = []

        # Prefix every rel_subdir with the input folder name so files
        # are written to <output_root>/<folder_name>/[subdir/]file
        folder_name = folder.name
        self._task_list = []
        for key, files in structure.items():
            if key == "root":
                rel = folder_name
            else:
                rel = str(Path(folder_name) / key)
            for f in files:
                self._task_list.append((f, rel))

        if total == 0:
            self._detect_label.setText("未偵測到可轉換的檔案")
            self._set_detect_variant("detect-warn")
            return

        all_files = [f for flist in structure.values() for f in flist]
        fmts = detect_formats(all_files)
        fmt_str = ", ".join(f.upper() for f in sorted(fmts))
        folder_part = (
            f"在 {folders} 個資料夾中" if folders > 1 else "在根目錄"
        )
        self._detect_label.setText(
            f"偵測到 {total} 個檔案 ({folder_part})，格式: {fmt_str}"
        )
        self._set_detect_variant("detect-ok")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_tasks(self) -> List[Tuple[Path, Optional[str]]]:
        return list(self._task_list)

    def get_output_dir(self) -> str:
        return self._output_full_path

    def get_output_fmt(self) -> str:
        return self._fmt_combo.currentText().lower()

    def get_values(self) -> Dict[str, Any]:
        return {
            "output_dir": self._output_full_path,
            "output_fmt": self.get_output_fmt(),
            "input_mode": self._input_mode,
            "input_dir": self._input_full_path if self._input_mode == "dir" else "",
            "input_files": list(self._custom_selected_files) if self._input_mode == "files" else [],
        }

    def set_values(self, values: Dict[str, Any]) -> None:
        if "output_dir" in values:
            self._output_full_path = values["output_dir"]
            _set_path_field(self.output_edit, values["output_dir"])
        if "output_fmt" in values:
            idx = self._fmt_combo.findText(values["output_fmt"].upper())
            if idx >= 0:
                self._fmt_combo.setCurrentIndex(idx)

        input_mode = values.get("input_mode", "none")
        if input_mode == "dir":
            saved_dir = values.get("input_dir", "")
            if saved_dir:
                self._set_folder(Path(saved_dir))
        elif input_mode == "files":
            saved_files = values.get("input_files", [])
            if saved_files:
                self._set_files([Path(p) for p in saved_files])
