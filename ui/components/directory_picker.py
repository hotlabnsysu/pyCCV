"""DirectoryPickerCard — shared 「檔案選取與輸出目錄」 card widget.

Instantiated by both BasicSettingsTab and ViewerTab so that path state is
visually identical.  Changes on either instance are propagated by the main
window via set_values() (signal-blocked to avoid feedback loops).
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QFileDialog,
)
from PySide6.QtCore import Qt, Signal

from config import SUPPORTED_IMAGE_FORMATS
from ..widgets import (
    make_clear_btn as _make_clear_btn,
    style_path_field as _style_path_field,
    shorten_path as _shorten_path,
    set_path_field as _set_path_field,
)
from ..tokens import FIELD_H as _FIELD_H


class DirectoryPickerCard(QWidget):
    """Card widget for input/output directory selection.

    Signals
    -------
    paths_changed(dict) — emitted whenever any path changes.
        dict keys: input_dir, output_dir, custom_select_enabled, custom_selected_images
    """

    paths_changed = Signal(dict)

    def __init__(self, settings: Dict[str, Any], parent: QWidget | None = None):
        super().__init__(parent)
        self.settings = settings
        self._custom_selected_images: List[str] = []
        self._input_mode: str = "dir"
        self._input_full_path: str = settings.get("input_dir", "")
        self._output_full_path: str = settings.get("output_dir", "")
        self._suppress_signal = False   # set True during set_values() to block feedback loops
        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        card = QWidget()
        card.setProperty("card", True)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 6, 10, 8)
        layout.setSpacing(5)
        header = QLabel("檔案選取與輸出目錄")
        header.setProperty("header", True)
        layout.addWidget(header)

        # ── 輸入目錄 / 選取檔案 ───────────────────────────────────────
        _saved_files = self.settings.get("custom_selected_images", [])
        if self.settings.get("custom_select_enabled", False) and _saved_files:
            self._input_mode = "files"
            self._custom_selected_images = list(_saved_files)
            _input_display = f"{len(_saved_files)} 個檔案"
        else:
            self._input_mode = "dir"
            _input_display = _shorten_path(self._input_full_path)

        self.input_dir_edit = QLineEdit(_input_display)
        _style_path_field(self.input_dir_edit)
        self.input_dir_edit.setPlaceholderText("點擊選取目錄")
        self.input_dir_edit.setToolTip(self._input_full_path)
        self.input_dir_edit.mousePressEvent = lambda e: self._browse_input()

        self._btn_input_files = QPushButton("選檔")
        self._btn_input_files.setFixedSize(38, _FIELD_H)
        self._btn_input_files.setToolTip("選取影像檔案 (可多選)")
        self._btn_input_files.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_input_files.setProperty("variant", "select")
        self._btn_input_files.clicked.connect(self._browse_input_files)

        self._btn_clear_input = _make_clear_btn()
        self._btn_clear_input.setVisible(bool(self.input_dir_edit.text()))
        self._btn_clear_input.clicked.connect(self._clear_input_dir)
        self.input_dir_edit.textChanged.connect(
            lambda t: self._btn_clear_input.setVisible(bool(t))
        )

        in_row = QHBoxLayout()
        in_row.setSpacing(4)
        in_row.addWidget(QLabel("輸入"), 0, Qt.AlignmentFlag.AlignVCenter)
        in_row.addWidget(self.input_dir_edit, stretch=1)
        in_row.addWidget(self._btn_input_files, 0, Qt.AlignmentFlag.AlignVCenter)
        in_row.addWidget(self._btn_clear_input, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(in_row)

        # ── 輸出目錄 ──────────────────────────────────────────────────
        self.output_dir_edit = QLineEdit(_shorten_path(self._output_full_path))
        _style_path_field(self.output_dir_edit)
        self.output_dir_edit.setPlaceholderText("點擊選取輸出目錄")
        self.output_dir_edit.setToolTip(self._output_full_path)
        self.output_dir_edit.mousePressEvent = lambda e: self._browse_output()

        self._btn_clear_output = _make_clear_btn()
        self._btn_clear_output.setVisible(bool(self.output_dir_edit.text()))
        self._btn_clear_output.clicked.connect(self._clear_output_dir)
        self.output_dir_edit.textChanged.connect(
            lambda t: self._btn_clear_output.setVisible(bool(t))
        )

        out_row = QHBoxLayout()
        out_row.setSpacing(4)
        out_row.addWidget(QLabel("輸出"), 0, Qt.AlignmentFlag.AlignVCenter)
        out_row.addWidget(self.output_dir_edit, stretch=1)
        out_row.addWidget(self._btn_clear_output, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(out_row)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(card)

    # ------------------------------------------------------------------
    # Browse / clear handlers
    # ------------------------------------------------------------------

    def _browse_input(self):
        start = self._input_full_path if self._input_mode == "dir" else ""
        path = QFileDialog.getExistingDirectory(self, "選擇輸入目錄", start)
        if path:
            self._input_mode = "dir"
            self._input_full_path = path
            self._custom_selected_images = []
            _set_path_field(self.input_dir_edit, path)
            self.input_dir_edit.setPlaceholderText("點擊選取目錄")
            self._emit_paths()

    def _browse_input_files(self):
        ext_list = " ".join([f"*{fmt}" for fmt in SUPPORTED_IMAGE_FORMATS])
        start = (
            str(Path(self._custom_selected_images[0]).parent)
            if self._input_mode == "files" and self._custom_selected_images
            else ""
        )
        files, _ = QFileDialog.getOpenFileNames(
            self, "選取影像檔案", start,
            f"影像檔案 ({ext_list});;所有檔案 (*.*)"
        )
        if files:
            self._input_mode = "files"
            self._custom_selected_images = list(files)
            self.input_dir_edit.setReadOnly(False)
            self.input_dir_edit.setText(f"{len(files)} 個檔案")
            self.input_dir_edit.setReadOnly(True)
            self._emit_paths()

    def _clear_input_dir(self):
        self._input_mode = "dir"
        self._input_full_path = ""
        self._custom_selected_images = []
        _set_path_field(self.input_dir_edit, "")
        self.input_dir_edit.setPlaceholderText("點擊選取目錄")
        self._emit_paths()

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "選擇輸出目錄", self._output_full_path)
        if path:
            self._output_full_path = path
            _set_path_field(self.output_dir_edit, path)
            self._emit_paths()

    def _clear_output_dir(self):
        self._output_full_path = ""
        _set_path_field(self.output_dir_edit, "")
        self._emit_paths()

    def _emit_paths(self):
        if not self._suppress_signal:
            self.paths_changed.emit(self.get_values())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_values(self) -> Dict[str, Any]:
        return {
            "input_dir": self._input_full_path if self._input_mode == "dir" else "",
            "output_dir": self._output_full_path,
            "custom_select_enabled": self._input_mode == "files",
            "custom_selected_images": list(self._custom_selected_images),
        }

    def set_values(self, values: Dict[str, Any]) -> None:
        """Update displayed paths without emitting paths_changed (to prevent feedback loops)."""
        self._suppress_signal = True
        try:
            if values.get("custom_select_enabled") and values.get("custom_selected_images"):
                self._input_mode = "files"
                self._custom_selected_images = list(values["custom_selected_images"])
                count = len(self._custom_selected_images)
                self.input_dir_edit.setReadOnly(False)
                self.input_dir_edit.setText(f"{count} 個檔案" if count else "")
                self.input_dir_edit.setReadOnly(True)
            elif "input_dir" in values:
                self._input_mode = "dir"
                self._input_full_path = values["input_dir"]
                self._custom_selected_images = []
                _set_path_field(self.input_dir_edit, values["input_dir"])
            if "output_dir" in values:
                self._output_full_path = values["output_dir"]
                _set_path_field(self.output_dir_edit, values["output_dir"])
        finally:
            self._suppress_signal = False
