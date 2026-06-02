# -*- coding: utf-8 -*-
"""QtLogHandler — 跨執行緒安全地把 Python logging record 推送至 UI log 窗。

Signal-slot 機制讓 worker thread 的 log 訊息自動在 main thread 的 GUI 事件迴圈中
接收，無需手動同步。UI 側透過 connect `log_emitted(html, levelno)` 接收：
  - html: 已依 level 染色的 HTML 片段 (可直接 appendHtml)
  - levelno: 原始 log level 數字 (供調用端自訂過濾或計數)
"""

from __future__ import annotations

import html
import logging
import time

from PySide6.QtCore import QObject, Signal

from services.logger import SUCCESS


# ── Level → 顯示標籤 / 顏色 ──────────────────────────────────────────────
_LEVEL_META = {
    logging.DEBUG:    ("DEBUG", "#858585"),
    logging.INFO:     ("INFO ", "#CCCCCC"),
    SUCCESS:          ("OK   ", "#4EC9B0"),
    logging.WARNING:  ("WARN ", "#E6A020"),
    logging.ERROR:    ("ERR  ", "#F14C4C"),
    logging.CRITICAL: ("CRIT ", "#F14C4C"),
}

_TIME_COLOR = "#858585"
_TEXT_COLOR = "#EAEAEA"


def format_record_html(record: logging.LogRecord) -> str:
    """Return an HTML line ready for QTextEdit.appendHtml()."""
    tag, tag_color = _LEVEL_META.get(record.levelno, ("LOG  ", "#CCCCCC"))
    ts = time.strftime("%H:%M:%S", time.localtime(record.created))
    msg = html.escape(record.getMessage())
    return (
        f'<span style="color:{_TIME_COLOR}">{ts}</span>&nbsp;&nbsp;'
        f'<b style="color:{tag_color}">{tag}</b>&nbsp;&nbsp;'
        f'<span style="color:{_TEXT_COLOR}">{msg}</span>'
    )


class QtLogHandler(QObject, logging.Handler):
    """logging.Handler that re-emits formatted records via a Qt Signal."""

    log_emitted = Signal(str)

    def __init__(self) -> None:
        QObject.__init__(self)
        logging.Handler.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            line = format_record_html(record)
        except Exception:
            self.handleError(record)
            return
        self.log_emitted.emit(line)
