# -*- coding: utf-8 -*-
"""pyCCV 集中式 logger。

多目的地輸出 (console / UI / rotating file)。呼叫端統一使用 `logger.info/warning/error`
或 `logger.log(SUCCESS, ...)`；UI 的 Qt handler 於 `ui/app.py` 啟動時由
`attach_qt_handler()` 掛上，避免在 import 時建立 QObject。
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

# ── 自訂 level ───────────────────────────────────────────────────────────
# 介於 INFO(20) 與 WARNING(30) 之間，表示「一個大流程正面完結」。
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")


def _success(self: logging.Logger, message: str, *args, **kwargs) -> None:
    if self.isEnabledFor(SUCCESS):
        self._log(SUCCESS, message, args, **kwargs)


logging.Logger.success = _success  # type: ignore[attr-defined]


# ── 檔案輸出路徑 ─────────────────────────────────────────────────────────
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE_PATH = _LOG_DIR / "pyCCV.log"


# ── Handler 建構 ────────────────────────────────────────────────────────
_CONSOLE_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_FILE_FMT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _build_console_handler() -> logging.Handler:
    h = logging.StreamHandler(sys.stdout)
    h.setLevel(logging.DEBUG)
    h.setFormatter(logging.Formatter(_CONSOLE_FMT, datefmt="%Y-%m-%d %H:%M:%S"))
    return h


def _build_rotating_file_handler() -> logging.Handler | None:
    # INFO level so per-pair DEBUG noise in the analysis loop never hits disk.
    try:
        h = logging.handlers.RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        h.setLevel(logging.INFO)
        h.setFormatter(logging.Formatter(_FILE_FMT, datefmt="%Y-%m-%d %H:%M:%S"))
        return h
    except OSError:
        return None


# ── 公開 API ────────────────────────────────────────────────────────────
def setup_logger(name: str = "pyCCV", level: int = logging.DEBUG) -> logging.Logger:
    """初始化 pyCCV logger (冪等)。Console + rotating file handlers。"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    if logger.handlers:
        return logger

    logger.addHandler(_build_console_handler())
    file_h = _build_rotating_file_handler()
    if file_h is not None:
        logger.addHandler(file_h)

    return logger


def attach_qt_handler(handler: logging.Handler, level: int = logging.INFO) -> None:
    """由 UI 啟動時呼叫，把 Qt handler 掛到 pyCCV logger (UI 僅顯示 INFO+)。"""
    logger = logging.getLogger("pyCCV")
    handler.setLevel(level)
    logger.addHandler(handler)


# 全域實例 (import 時建立 console + file handler；UI handler 由 app.py 後掛)
logger = setup_logger()
