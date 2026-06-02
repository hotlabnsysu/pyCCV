"""ConvertViewController — owns conversion tab logic."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, Slot
from PySide6.QtWidgets import QMessageBox

from services.logger import logger


class ConvertViewController:
    """Extracts conversion logic from PyCCVMainWindow."""

    def __init__(self, view, tab_convert, convert_service):
        self._view = view
        self._tab = tab_convert
        self._service = convert_service
        self._is_closing = False

        self._service.progress.connect(self._on_progress)
        self._service.completed.connect(self._on_complete)

    def set_closing(self, v: bool) -> None:
        self._is_closing = v

    def start(self) -> None:
        if self._service.is_running:
            return

        tasks = self._tab.get_tasks()
        output_dir = self._tab.get_output_dir()
        output_fmt = self._tab.get_output_fmt()

        if not tasks:
            QMessageBox.critical(self._view, "錯誤", "請先選取輸入檔案或資料夾")
            return
        if not output_dir:
            QMessageBox.critical(self._view, "錯誤", "請選取輸出目錄")
            return

        self._view.btn_start.setEnabled(False)
        self._view.progress_bar.setValue(0)
        self._view.progress_text.setText("啟動中...")
        self._view.current_file_label.setText("")
        self._service.run_conversion(
            tasks=tasks,
            output_root=Path(output_dir),
            output_fmt=output_fmt,
        )

    def stop(self) -> None:
        if not self._service.is_running:
            return
        button = QMessageBox.question(
            self._view, "停止", "確定停止轉換?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if button != QMessageBox.StandardButton.Yes:
            return
        self._service.stop()
        self._view.btn_pause.setText("暫停")
        logger.info("停止中...")

    def pause(self) -> None:
        if not self._service.is_running:
            return
        if self._service.is_paused:
            self._service.resume()
            self._view.btn_pause.setText("暫停")
            logger.info("繼續轉換")
        else:
            self._service.pause()
            self._view.btn_pause.setText("繼續")
            logger.info("暫停轉換")

    @Slot(int, int)
    def _on_progress(self, current: int, total: int) -> None:
        if self._is_closing:
            return
        pct = current / total if total > 0 else 0
        self._view.progress_bar.setValue(int(pct * 1000))
        self._view.progress_text.setText(f"進度 {pct*100:.1f}% ({current}/{total})")
        self._view.current_file_label.setText(f"已轉換 {current} / {total}")

    @Slot(str, bool)
    def _on_complete(self, total_time_str: str, cancelled: bool) -> None:
        if self._is_closing:
            return
        self._view.btn_start.setEnabled(True)
        self._view.btn_pause.setText("暫停")
        if cancelled:
            self._view.progress_text.setText("已停止")
        else:
            self._view.progress_text.setText(f"完成! ({total_time_str})")
            QTimer.singleShot(
                50,
                lambda: QMessageBox.information(
                    self._view, "完成", f"轉換已完成\n總耗時: {total_time_str}"
                ) if not self._is_closing else None,
            )

    def shutdown(self) -> None:
        self._service.shutdown()
