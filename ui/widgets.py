# -*- coding: utf-8 -*-
"""pyCCV 自訂 UI 控制元件與共用 QSS 常數"""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox, QStyle, QStylePainter, QStyleOptionComboBox,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon

from .tokens import FIELD_H, LABEL_GAP

_ICON_CLEAR = str(Path(__file__).parent.parent / "assets" / "icons" / "ic_clear.svg")
_ICON_SIZE = QSize(14, 14)


def shorten_path(full_path: str) -> str:
    """Show only the last 2 folder levels, e.g. '…\\parent\\folder'."""
    if not full_path:
        return full_path
    parts = Path(full_path).parts
    if len(parts) <= 2:
        return full_path
    return "…\\" + str(Path(*parts[-2:]))


def set_path_field(field: QLineEdit, full_path: str) -> None:
    """Update a read-only path field: shortened display text + full-path tooltip."""
    field.setReadOnly(False)
    field.setText(shorten_path(full_path))
    field.setReadOnly(True)
    field.setToolTip(full_path)


def form_row(label_text: str, widget: QWidget, label_width: int,
             extra_widgets: list | None = None,
             add_stretch: bool = True) -> QHBoxLayout:
    """產生一個 label (固定寬、右對齊) + widget(+可選額外 widget) + stretch 的水平 layout。

    用於卡片內 label 欄對齊：同一卡片內所有 form_row 應傳入相同 label_width，
    即可確保輸入元件左緣對齊。

    Parameters
    ----------
    label_text : str
        Label 顯示文字
    widget : QWidget
        主輸入元件
    label_width : int
        Label 欄固定寬度 (px)
    extra_widgets : list[QWidget] | None
        Label 之後、stretch 之前要追加的額外元件 (例如 slider+spin 組合)
    add_stretch : bool
        是否在末尾加 stretch (推左)，預設 True
    """
    row = QHBoxLayout()
    row.setSpacing(LABEL_GAP)
    lbl = QLabel(label_text)
    lbl.setFixedWidth(label_width)
    lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    row.addWidget(lbl)
    row.addWidget(widget)
    if extra_widgets:
        for w in extra_widgets:
            row.addWidget(w)
    if add_stretch:
        row.addStretch()
    return row


class CenteredComboBox(QComboBox):
    """覆寫 paintEvent，讓目前選取項目文字在整個元件內水平置中。
    先畫外框/背景/箭頭，再以整個 widget 的 rect() 為基準繪製置中文字，
    這樣文字視覺上會落在元件中線，而不是扣掉下拉按鈕後的 edit field 中線。
    """

    def paintEvent(self, event):  # noqa: N802
        painter = QStylePainter(self)
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        # 先畫外框/背景/下拉箭頭（不畫文字）
        painter.drawComplexControl(QStyle.ComplexControl.CC_ComboBox, opt)
        # 以 widget rect 為基準、稍微扣掉右側下拉箭頭的視覺重量，讓文字往左偏一點
        painter.setPen(self.palette().text().color())
        painter.drawText(
            self.rect().adjusted(0, 0, -10, 0),
            Qt.AlignmentFlag.AlignCenter,
            self.currentText(),
        )


# ── 下拉箭頭圖示 ──────────────────────────────────────────────────────────
_ARROW_DOWN = (Path(__file__).parent.parent / "assets" / "icons" / "ic_arrow_down.svg").as_posix()


# ── MODISQ-style shared QSS constants ─────────────────────────────────────

COMBO_QSS = f"""
QComboBox {{
    background-color: #2D2D2D;
    color: #EAEAEA;
    border: 1px solid #4A4A4A;
    border-radius: 4px;
    padding: 0px 2px;
    font-size: 12px;
    min-height: 0px;
}}
QComboBox:hover {{
    border-color: #008CE6;
    background-color: rgba(0, 140, 230, 0.15);
}}
QComboBox:focus {{
    border-color: #008CE6;
    color: #EAEAEA;
}}
QComboBox::drop-down {{
    width: 18px;
    border: none;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}
QComboBox::down-arrow {{
    image: url({_ARROW_DOWN});
    width: 10px;
    height: 10px;
}}
QComboBox QAbstractItemView {{
    selection-background-color: #007ACC;
    selection-color: #FFFFFF;
    border: 1px solid #4A4A4A;
    font-size: 12px;
}}
QComboBox:disabled {{ color: #858585; }}
"""

SPIN_QSS = """
QDoubleSpinBox, QSpinBox {
    background: #2D2D2D;
    color: #EAEAEA;
    border: 1px solid #4A4A4A;
    border-radius: 4px;
    padding: 0px 2px;
    font-size: 12px;
    min-height: 0px;
}
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button,
QSpinBox::up-button, QSpinBox::down-button {
    width: 18px;
    border: none;
    background: #4A4A4A;
}
QDoubleSpinBox::up-button, QSpinBox::up-button {
    subcontrol-position: top right;
    border-bottom: 1px solid #333333;
    border-top-right-radius: 3px;
}
QDoubleSpinBox::down-button, QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 3px;
}
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover,
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background: rgba(0, 140, 230, 0.15);
}
QDoubleSpinBox::up-button:pressed, QDoubleSpinBox::down-button:pressed,
QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
    background: #007ACC;
}
QDoubleSpinBox::up-arrow, QSpinBox::up-arrow   { width: 7px; height: 5px; }
QDoubleSpinBox::down-arrow, QSpinBox::down-arrow { width: 7px; height: 5px; }
QDoubleSpinBox:disabled, QSpinBox:disabled { color: #858585; }
"""

PATH_QSS = """
QLineEdit {
    background-color: #2D2D2D;
    border: 1px solid #4A4A4A;
    border-radius: 4px;
    padding: 0px 4px;
    font-size: 12px;
    min-height: 0px;
    color: #EAEAEA;
}
QLineEdit:hover {
    border-color: #008CE6;
    background-color: rgba(0, 140, 230, 0.15);
}
QLineEdit:disabled {
    color: #858585;
    border-color: #333333;
    background-color: #202020;
}
"""

CLEAR_BTN_QSS = """
QPushButton {
    background-color: transparent;
    border: none;
    border-radius: 4px;
    padding: 2px;
}
QPushButton:hover { background-color: rgba(255, 0, 60, 0.15); }
QPushButton:pressed { background-color: rgba(255, 0, 60, 0.30); }
QPushButton:disabled { background-color: transparent; }
"""


def make_clear_btn() -> QPushButton:
    """Build the standard ✕ clear button (initially hidden)."""
    btn = QPushButton()
    btn.setFixedSize(FIELD_H, FIELD_H)
    btn.setIcon(QIcon(_ICON_CLEAR))
    btn.setIconSize(_ICON_SIZE)
    btn.setToolTip("清除")
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.setStyleSheet(CLEAR_BTN_QSS)
    btn.setVisible(False)
    return btn


def style_path_field(field: QLineEdit) -> None:
    """Apply shared read-only clickable-path styling to a QLineEdit."""
    field.setReadOnly(True)
    field.setFixedHeight(FIELD_H)
    field.setCursor(Qt.CursorShape.PointingHandCursor)
    field.setStyleSheet(PATH_QSS)
