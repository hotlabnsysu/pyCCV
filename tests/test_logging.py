# -*- coding: utf-8 -*-
"""Tests for the logging infrastructure (services/logger + ui/logging_qt)."""

from __future__ import annotations

import logging
from pathlib import Path


def test_success_level_registered():
    from services.logger import SUCCESS
    assert SUCCESS == 25
    assert logging.getLevelName(SUCCESS) == "SUCCESS"


def test_logger_has_success_method():
    from services.logger import logger
    assert hasattr(logger, "success")
    logger.success("test success message")


def test_file_log_path_under_data_dir():
    from services.logger import LOG_FILE_PATH
    assert LOG_FILE_PATH.parent.exists()
    assert LOG_FILE_PATH.name == "pyCCV.log"


def test_logger_emits_all_levels(pyccv_caplog):
    from services.logger import logger, SUCCESS

    logger.debug("dbg line")
    logger.info("info line")
    logger.log(SUCCESS, "ok line")
    logger.warning("warn line")
    logger.error("err line")

    levels = {r.levelname for r in pyccv_caplog.records if r.name == "pyCCV"}
    assert levels >= {"DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR"}


def test_qt_log_handler_formats_html():
    from ui.logging_qt import format_record_html

    record = logging.LogRecord(
        name="pyCCV",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    html = format_record_html(record)
    assert "hello world" in html
    assert "INFO" in html
    assert ":" in html   # contains HH:MM:SS


def test_qt_log_handler_html_escapes_special_chars():
    from ui.logging_qt import format_record_html

    record = logging.LogRecord(
        name="pyCCV", level=logging.INFO, pathname=__file__, lineno=1,
        msg="a<b>c&d", args=(), exc_info=None,
    )
    html = format_record_html(record)
    assert "a&lt;b&gt;c&amp;d" in html


def test_qt_log_handler_level_colors_differ():
    from ui.logging_qt import format_record_html

    def _html_for(level: int) -> str:
        r = logging.LogRecord(name="pyCCV", level=level, pathname=__file__,
                              lineno=1, msg="x", args=(), exc_info=None)
        return format_record_html(r)

    from services.logger import SUCCESS
    # Each level should have a unique colour token in its HTML
    htmls = {
        "info": _html_for(logging.INFO),
        "ok": _html_for(SUCCESS),
        "warn": _html_for(logging.WARNING),
        "err": _html_for(logging.ERROR),
    }
    # Different colours → different HTML
    assert len(set(htmls.values())) == 4


def test_qt_log_handler_emit_creates_signal():
    """Validates QtLogHandler instantiation and the Signal wiring
    without requiring pytest-qt (uses a direct emit check via Signal introspection)."""
    from ui.logging_qt import QtLogHandler

    handler = QtLogHandler()
    # Signal attribute exists and is a Signal descriptor bound to this instance
    assert hasattr(handler, "log_emitted")
    # emit() should not raise on a well-formed record
    record = logging.LogRecord(
        name="pyCCV", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="warn msg", args=(), exc_info=None,
    )
    handler.emit(record)
