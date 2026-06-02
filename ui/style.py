"""
pyCCV PySide6 UI 樣式表
基於 Visual Studio Dark 主題風格（移植自 MODISQ）
"""

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont, QPalette, QColor


def apply_theme(app: QApplication) -> None:
    """套用全域主題：Fusion style + QPalette + QSS"""
    app.setStyle("Fusion")

    # 全局字型
    font = QFont()
    font.setFamilies(["Segoe UI", "Microsoft JhengHei", "Microsoft JhengHei UI", "Arial", "sans-serif"])
    font.setPixelSize(13)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    font.setHintingPreference(QFont.HintingPreference.PreferVerticalHinting)
    app.setFont(font)

    # 全局調色盤（dark VS Code）
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window,          QColor("#252526"))
    palette.setColor(QPalette.ColorRole.WindowText,      QColor("#EAEAEA"))
    palette.setColor(QPalette.ColorRole.Base,            QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#2D2D2D"))
    palette.setColor(QPalette.ColorRole.Text,            QColor("#EAEAEA"))
    palette.setColor(QPalette.ColorRole.Button,          QColor("#383838"))
    palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#EAEAEA"))
    palette.setColor(QPalette.ColorRole.Highlight,       QColor("#264F78"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#EAEAEA"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#858585"))
    palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#181818"))
    palette.setColor(QPalette.ColorRole.ToolTipText,     QColor("#EAEAEA"))
    app.setPalette(palette)

    app.setStyleSheet(QSS)


QSS = """
/* ===================================================
   全局基礎
=================================================== */
QWidget {
    background-color: #202020;
    color: #EAEAEA;
    font-family: "Segoe UI", "Microsoft JhengHei", "Microsoft JhengHei UI", sans-serif;
    font-size: 13px;
    selection-background-color: #264F78;
    selection-color: #EAEAEA;
}

/* 所有 QLabel 預設透明背景，避免在卡片內顯示深色矩形 */
QLabel {
    background: transparent;
}
QCheckBox {
    background: transparent;
}
QRadioButton {
    background: transparent;
}

/* ===================================================
   卡片容器
=================================================== */
QWidget[card="true"] {
    background-color: #2D2D2D;
    border: 1px solid #333333;
    border-radius: 4px;
}

/* ===================================================
   卡片標題
=================================================== */
QLabel[header="true"] {
    color: #FFFFFF;
    font-size: 13px;
    font-weight: bold;
    border-bottom: 1px solid #4A4A4A;
    padding-bottom: 4px;
    margin-bottom: 2px;
    background: transparent;
}

/* 次要提示文字 (建議值、單位說明) */
QLabel[variant="hint"] {
    color: #64748B;
    font-size: 12px;
    background: transparent;
}

/* 偵測結果文字 (SERVICE tab) */
QLabel[variant="detect"] { color: #64748B; font-size: 13px; background: transparent; }
QLabel[variant="detect-ok"] { color: #EAEAEA; font-size: 13px; background: transparent; }
QLabel[variant="detect-warn"] { color: #E6A020; font-size: 13px; background: transparent; }

/* ===================================================
   QPushButton 全狀態
=================================================== */
QPushButton {
    background-color: #383838;
    color: #EAEAEA;
    border: 1px solid #4A4A4A;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: normal;
    min-height: 24px;
}
QPushButton:hover {
    background-color: #3C3C3C;
    border-color: #666666;
}
QPushButton:pressed {
    background-color: #264F78;
    border-color: #008CE6;
}
QPushButton:checked {
    background-color: #007ACC;
    color: #FFFFFF;
    border: 1px solid #007ACC;
}
QPushButton:checked:hover {
    background-color: #0098FF;
    border-color: #0098FF;
}
QPushButton:disabled {
    background-color: #202020;
    color: #858585;
    border-color: #333333;
}

/* Tab 按鈕 */
QPushButton[role="tab"] {
    border-radius: 4px 4px 0px 0px;
    min-height: 22px;
    background-color: #2D2D2D;
    color: #858585;
    border: none;
    border-right: 1px solid #333333;
    border-bottom: 1px solid #333333;
    font-size: 12px;
    font-weight: normal;
    padding: 3px 14px;
}
QPushButton[role="tab"]:hover {
    background-color: #2D2D2D;
    color: #EAEAEA;
}
QPushButton[role="tab"]:checked {
    background-color: #181818;
    color: #FFFFFF;
    border: none;
    border-top: 2px solid #008CE6;
    border-right: 1px solid #333333;
    font-weight: bold;
}

/* ===================================================
   動作按鈕（停止 / 暫停 / 開始分析）
=================================================== */

/* 危險按鈕（停止）— ghost 輪廓風格 */
QPushButton[role="danger"] {
    background-color: transparent;
    color: #F14C4C;
    border: 1px solid #5A1F1F;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    padding: 3px 14px;
}
QPushButton[role="danger"]:hover {
    background-color: rgba(241, 76, 76, 0.12);
    border-color: #B03030;
    color: #FF6B6B;
}
QPushButton[role="danger"]:pressed {
    background-color: rgba(241, 76, 76, 0.25);
    border-color: #F14C4C;
}
QPushButton[role="danger"]:disabled {
    background-color: transparent;
    color: #555555;
    border-color: #3A3A3A;
}

/* 成功按鈕（開始分析）— 實心主要動作 */
QPushButton[role="success"] {
    background-color: #007ACC;
    color: #FFFFFF;
    border: none;
    border-radius: 4px;
    font-size: 12px;
    font-weight: bold;
    padding: 3px 16px;
    min-width: 90px;
}
QPushButton[role="success"]:hover {
    background-color: #0090E8;
}
QPushButton[role="success"]:pressed {
    background-color: #005F9E;
}
QPushButton[role="success"]:disabled {
    background-color: #1E3A50;
    color: #555555;
    border: none;
}

/* 警告按鈕（暫停）— ghost 輪廓風格 */
QPushButton[role="warning"] {
    background-color: transparent;
    color: #E5B800;
    border: 1px solid #4A3C00;
    border-radius: 4px;
    font-size: 12px;
    font-weight: 600;
    padding: 3px 14px;
}
QPushButton[role="warning"]:hover {
    background-color: rgba(229, 184, 0, 0.12);
    border-color: #9A8000;
    color: #FFD740;
}
QPushButton[role="warning"]:pressed {
    background-color: rgba(229, 184, 0, 0.25);
    border-color: #E5B800;
}
QPushButton[role="warning"]:disabled {
    background-color: transparent;
    color: #555555;
    border-color: #3A3A3A;
}

/* ===================================================
   QCheckBox
=================================================== */
QCheckBox {
    spacing: 8px;
    color: #CCCCCC;
}
QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border-radius: 2px;
    border: 1px solid #4A4A4A;
    background-color: #383838;
}
QCheckBox::indicator:hover {
    border-color: #008CE6;
}
QCheckBox::indicator:checked {
    background-color: #008CE6;
    border-color: #008CE6;
}
QCheckBox::indicator:checked:hover {
    background-color: #0098FF;
    border-color: #0098FF;
}
QCheckBox:disabled {
    color: #858585;
}
QCheckBox::indicator:disabled {
    border-color: #333333;
    background-color: #202020;
}

/* ===================================================
   QRadioButton
=================================================== */
QRadioButton {
    spacing: 8px;
    color: #CCCCCC;
}
QRadioButton::indicator {
    width: 13px;
    height: 13px;
    border-radius: 7px;
    border: 1px solid #4A4A4A;
    background-color: #383838;
}
QRadioButton::indicator:checked {
    background-color: #008CE6;
    border-color: #008CE6;
}
QRadioButton::indicator:hover {
    border-color: #008CE6;
}
QRadioButton:disabled {
    color: #858585;
}

/* ===================================================
   QLineEdit
=================================================== */
QLineEdit {
    background-color: #383838;
    border: 1px solid #4A4A4A;
    border-radius: 3px;
    padding: 4px 8px;
    min-height: 24px;
    color: #EAEAEA;
}
QLineEdit:hover {
    border-color: #666666;
}
QLineEdit:focus {
    border-color: #008CE6;
    background-color: #202020;
}
QLineEdit:disabled {
    background-color: #202020;
    color: #858585;
    border-color: #333333;
}

/* 路徑輸入格 — MODISQ 風格：藍色 hover accent */
QLineEdit[role="path"] {
    background-color: #2D2D2D;
    border: 1px solid #4A4A4A;
    border-radius: 4px;
    padding: 0px 4px;
    font-size: 12px;
    color: #EAEAEA;
}
QLineEdit[role="path"]:hover {
    border-color: #008CE6;
    background-color: rgba(0, 140, 230, 0.10);
}
QLineEdit[role="path"]:focus {
    border-color: #008CE6;
    background-color: #202020;
}
QLineEdit[role="path"]:disabled {
    background-color: #202020;
    color: #858585;
    border-color: #333333;
}

/* ===================================================
   QSpinBox / QDoubleSpinBox
=================================================== */
QSpinBox, QDoubleSpinBox {
    background-color: #383838;
    border: 1px solid #4A4A4A;
    border-radius: 3px;
    padding: 0px 22px 0px 8px;
    min-height: 24px;
    color: #EAEAEA;
}
QSpinBox:hover, QDoubleSpinBox:hover {
    border-color: #666666;
}
QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #008CE6;
    background-color: #202020;
}
QSpinBox:disabled, QDoubleSpinBox:disabled {
    background-color: #202020;
    color: #858585;
}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    width: 16px;
    background-color: transparent;
    border: none;
}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #4A4A4A;
}
QSpinBox::up-button:pressed, QDoubleSpinBox::up-button:pressed,
QSpinBox::down-button:pressed, QDoubleSpinBox::down-button:pressed {
    background-color: #007ACC;
}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
    width: 7px;
    height: 7px;
}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 7px;
    height: 7px;
}

/* ===================================================
   QComboBox
=================================================== */
QComboBox {
    background-color: #383838;
    border: 1px solid #4A4A4A;
    border-radius: 3px;
    padding: 4px 28px 4px 8px;
    min-height: 24px;
    color: #EAEAEA;
}
QComboBox:hover {
    border-color: #666666;
}
QComboBox:focus {
    border-color: #008CE6;
    background-color: #202020;
}
QComboBox:disabled {
    background-color: #202020;
    color: #858585;
}
QComboBox::drop-down {
    width: 20px;
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #2D2D2D;
    border: 1px solid #4A4A4A;
    selection-background-color: #264F78;
    selection-color: #EAEAEA;
    color: #EAEAEA;
    padding: 4px;
}

/* ===================================================
   QProgressBar
=================================================== */
QProgressBar {
    background-color: #333333;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #008CE6;
    border-radius: 4px;
}

/* ===================================================
   QSlider
=================================================== */
QSlider::groove:horizontal {
    height: 5px;
    background-color: #4A4A4A;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 8px;
    height: 20px;
    margin: -7px 0;
    background-color: #EAEAEA;
    border: none;
    border-radius: 3px;
}
QSlider::handle:horizontal:hover {
    background-color: #FFFFFF;
}
QSlider::sub-page:horizontal {
    background-color: #008CE6;
    border-radius: 2px;
}
QSlider::groove:horizontal:disabled {
    background-color: #333333;
}
QSlider::sub-page:horizontal:disabled {
    background-color: #4A4A4A;
}
QSlider::handle:horizontal:disabled {
    background-color: #383838;
}

/* ===================================================
   QPlainTextEdit / QTextEdit（日誌區）
=================================================== */
QPlainTextEdit, QTextEdit {
    background-color: transparent;
    border: none;
    color: #CE9178;
    font-family: 'Courier New', Consolas, monospace;
    font-size: 12px;
}

/* Log pane — HTML coloring is applied per-line by QtLogHandler;
   keep widget-level color neutral so defaults don't override spans. */
QTextEdit[variant="log"] {
    background-color: transparent;
    border: none;
    color: #EAEAEA;
    font-family: 'Courier New', Consolas, monospace;
    font-size: 12px;
}

/* ===================================================
   QScrollBar（極簡 VS Code 風格）
=================================================== */
QScrollBar:vertical {
    width: 12px;
    background: transparent;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #424242;
    border-radius: 6px;
    min-height: 30px;
    margin: 2px;
}
QScrollBar::handle:vertical:hover {
    background: #4F4F4F;
}
QScrollBar::handle:vertical:pressed {
    background: #5B5B5B;
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    height: 12px;
    background: transparent;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #424242;
    border-radius: 6px;
    min-width: 30px;
    margin: 2px;
}
QScrollBar::handle:horizontal:hover {
    background: #4F4F4F;
}
QScrollBar::handle:horizontal:pressed {
    background: #5B5B5B;
}
QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ===================================================
   QToolTip
=================================================== */
QToolTip {
    background-color: #181818;
    color: #EAEAEA;
    border: 1px solid #4A4A4A;
    border-radius: 3px;
    padding: 6px 8px;
}

/* ===================================================
   QScrollArea（透明背景）
=================================================== */
QScrollArea {
    border: none;
    background: transparent;
}
QScrollArea > QWidget > QWidget {
    background: transparent;
}

/* ===================================================
   QSplitter
=================================================== */
QSplitter::handle {
    background-color: #333333;
}

/* ===================================================
   按鈕 variant (集中取代各 tab 的 inline QSS)
=================================================== */

/* 選檔 / 清除 等中性瀏覽按鈕 */
QPushButton[variant="select"] {
    background-color: #2D2D2D;
    color: #EAEAEA;
    border: 1px solid #4A4A4A;
    border-radius: 4px;
    padding: 0px 4px;
    font-size: 12px;
    min-height: 0px;
}
QPushButton[variant="select"]:hover {
    border-color: #008CE6;
    background-color: rgba(0, 140, 230, 0.15);
}
QPushButton[variant="select"]:pressed {
    background-color: #264F78;
    border-color: #008CE6;
}

/* 導覽/播放/清除 等小型中性操作按鈕 (VIEW 播放列) */
QPushButton[variant="nav"] {
    background-color: #2D2D2D;
    color: #EAEAEA;
    border: 1px solid #4A4A4A;
    border-radius: 4px;
    padding: 0px 8px;
    font-size: 12px;
    min-height: 0px;
}
QPushButton[variant="nav"]:hover {
    border-color: #008CE6;
    background-color: rgba(0, 140, 230, 0.15);
}
QPushButton[variant="nav"]:pressed {
    background-color: #264F78;
    border-color: #008CE6;
}

/* 掃描檔案 — 暗紅 (警示意涵，重新掃描會重設結果) */
QPushButton[variant="scan"] {
    background-color: #802020;
    color: #FFFFFF;
    border: 1px solid #9A3030;
    border-radius: 4px;
    padding: 0px 8px;
    font-size: 12px;
    min-height: 0px;
}
QPushButton[variant="scan"]:hover { background-color: #9A2828; }
QPushButton[variant="scan"]:pressed { background-color: #601818; }

/* 繪圖 — 綠 (執行/確認語意) */
QPushButton[variant="plot"] {
    background-color: #00885A;
    color: #FFFFFF;
    border: 1px solid #00AA70;
    border-radius: 4px;
    padding: 0px 8px;
    font-size: 12px;
    min-height: 0px;
}
QPushButton[variant="plot"]:hover { background-color: #009966; }
QPushButton[variant="plot"]:pressed { background-color: #007050; }

/* Segmented 按鈕 (mutually-exclusive 分段控制, 如 影像/向量/渦度) */
QPushButton[segmented="true"] {
    background-color: #2D2D2D;
    color: #AAAAAA;
    border: 1px solid #4A4A4A;
    border-radius: 3px;
    padding: 0px 10px;
    font-size: 12px;
    font-weight: normal;
    min-height: 0px;
}
QPushButton[segmented="true"]:hover {
    border-color: #008CE6;
    background-color: rgba(0, 140, 230, 0.20);
    color: #EAEAEA;
}
QPushButton[segmented="true"]:checked {
    background-color: #264F78;
    color: #FFFFFF;
    border-color: #008CE6;
}
QPushButton[segmented="true"]:checked:hover {
    background-color: #007ACC;
    border-color: #008CE6;
}
QPushButton[segmented="true"]:disabled {
    background-color: #232323;
    color: #555555;
    border-color: #333333;
}

/* 範圍數字輸入 (Min/Max colorbar edits) */
QLineEdit[variant="range"] {
    background-color: #2D2D2D;
    color: #EAEAEA;
    border: 1px solid #4A4A4A;
    border-radius: 4px;
    padding: 0px 3px;
    font-size: 12px;
    font-weight: normal;
    min-height: 0px;
}
QLineEdit[variant="range"]:hover { border-color: #008CE6; }
QLineEdit[variant="range"]:focus { border-color: #008CE6; }
QLineEdit[variant="range"]:disabled {
    background-color: #232323;
    color: #555555;
    border-color: #333333;
}
"""
