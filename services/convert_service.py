"""ConvertService — 格式轉換服務

使用 Python `threading.Thread` (與前身專案 pyCCV v1.2 Converter 相同模式)，
避免 QThread + scipy native code 在 Windows 上的相容性問題。
"""

from __future__ import annotations

import datetime
import os
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QObject, Qt, Signal

from services.logger import logger, SUCCESS
from shared.io_formats import (
    load_flo,
    load_mat,
    load_npz,
    load_raw_custom,
    save_flo,
    save_mat,
    save_npz,
    save_raw_custom,
)

SUPPORTED_CONVERT_FORMATS: List[str] = ["npz", "flo", "mat", "raw"]


# ── File I/O helpers ──────────────────────────────────────────────────────────

def _load_file(path: Path) -> Dict:
    suffix = path.suffix.lower()
    if suffix == ".npz":
        return load_npz(path)
    if suffix == ".flo":
        return load_flo(path, with_grid=True)
    if suffix == ".mat":
        return load_mat(path)
    if suffix == ".raw":
        return load_raw_custom(path)
    raise ValueError(f"不支援的格式: {suffix}")


def _save_file(path: Path, data: Dict, fmt: str) -> None:
    save_path = path.with_suffix(f".{fmt}")
    save_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "npz":
        save_npz(save_path, data)
    elif fmt == "flo":
        save_flo(save_path, data)
    elif fmt == "mat":
        save_mat(save_path, data)
    elif fmt == "raw":
        save_raw_custom(save_path, data)
    else:
        raise ValueError(f"不支援的輸出格式: {fmt}")


# ── Scan helpers ──────────────────────────────────────────────────────────────

def scan_folder_recursive(
    root_path: Path,
) -> Tuple[Dict[str, List[Path]], int, int]:
    """掃描資料夾 (含子資料夾) 中所有可轉換檔案。"""
    extensions = tuple(f".{fmt}" for fmt in SUPPORTED_CONVERT_FORMATS)
    structure: Dict[str, List[Path]] = {}
    total_files = 0
    total_folders = 0

    for dirpath, _, filenames in os.walk(root_path):
        valid = [
            Path(dirpath) / f
            for f in filenames
            if f.lower().endswith(extensions)
        ]
        if not valid:
            continue
        try:
            rel = Path(dirpath).relative_to(root_path)
        except ValueError:
            rel = Path(".")
        key = str(rel) if str(rel) != "." else "root"
        structure[key] = sorted(valid)
        total_files += len(valid)
        total_folders += 1

    return structure, total_files, total_folders


def scan_files_list(
    files: List[str],
) -> Tuple[List[Path], int]:
    """過濾出可轉換格式的檔案清單。"""
    extensions = tuple(f".{fmt}" for fmt in SUPPORTED_CONVERT_FORMATS)
    valid = [Path(f) for f in files if str(f).lower().endswith(extensions)]
    return sorted(valid), len(valid)


def detect_formats(files: List[Path]) -> Set[str]:
    return {f.suffix.lower().lstrip(".") for f in files}


# ── Service ───────────────────────────────────────────────────────────────────

class ConvertService(QObject):
    """格式轉換服務。

    Runs conversion in a plain Python `threading.Thread` (matching the
    behaviour of the predecessor pyCCV v1.2 Converter, which is known to work
    reliably on Windows). Progress/log/completion are delivered via Qt signals
    with QueuedConnection so slots execute on the main thread.
    """

    progress = Signal(int, int)          # current, total
    completed = Signal(str, bool)        # time_str, was_cancelled

    def __init__(self):
        super().__init__()
        self.is_running = False
        self.is_paused = False
        self._shutdown = False
        self._was_cancelled = False
        self._resume_event = threading.Event()
        self._resume_event.set()

        self._tasks: List[Tuple[Path, Optional[str]]] = []
        self._output_root: Path = Path(".")
        self._output_fmt: str = "npz"

        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_conversion(
        self,
        tasks: List[Tuple[Path, Optional[str]]],
        output_root: Path,
        output_fmt: str,
    ) -> None:
        """Non-blocking: kicks off conversion in a background Python thread."""
        if self.is_running:
            return

        self.is_running = True
        self.is_paused = False
        self._shutdown = False
        self._was_cancelled = False
        self._resume_event.set()
        self._tasks = tasks
        self._output_root = output_root
        self._output_fmt = output_fmt

        self._thread = threading.Thread(
            target=self._conversion_loop,
            name="pyCCV-Convert",
            daemon=True,
        )
        self._thread.start()

    def pause(self) -> None:
        self.is_paused = True
        self._resume_event.clear()

    def resume(self) -> None:
        self.is_paused = False
        self._resume_event.set()

    def stop(self) -> None:
        self.is_running = False
        self._shutdown = True
        self._was_cancelled = True
        self._resume_event.set()

    def shutdown(self) -> None:
        self.stop()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(3.0)

    # ------------------------------------------------------------------
    # Thread-safe emit helpers
    # ------------------------------------------------------------------
    # Emitting from a non-Qt thread is safe: the auto-connection mechanism
    # detects the cross-thread boundary and queues the delivery to the main
    # thread where this QObject was constructed.

    def _emit_progress(self, current: int, total: int) -> None:
        try:
            self.progress.emit(current, total)
        except RuntimeError:
            pass

    def _emit_completed(self, time_str: str, cancelled: bool) -> None:
        try:
            self.completed.emit(time_str, cancelled)
        except RuntimeError:
            pass

    # ------------------------------------------------------------------
    # Worker body (runs inside threading.Thread)
    # ------------------------------------------------------------------

    def _conversion_loop(self) -> None:
        start_time = time.time()
        tasks = self._tasks
        output_root = self._output_root
        output_fmt = self._output_fmt
        total = len(tasks)
        success = 0
        fail = 0

        try:
            logger.info("轉換開始 | 檔案=%d | 格式=.%s | 輸出=%s",
                        total, output_fmt.upper(), output_root)

            for i, (src_path, rel_subdir) in enumerate(tasks):
                if self._shutdown:
                    break

                while not self._resume_event.wait(timeout=0.5):
                    if self._shutdown:
                        break
                if self._shutdown:
                    break

                try:
                    data = _load_file(src_path)
                    save_dir = (
                        output_root / rel_subdir if rel_subdir else output_root
                    )
                    _save_file(save_dir / src_path.stem, data, output_fmt)
                    success += 1
                    logger.debug("轉換成功 %s", src_path.name)
                except BaseException as exc:
                    fail += 1
                    logger.error("轉換失敗 | 檔案=%s | 原因=%s", src_path.name, exc)

                self._emit_progress(i + 1, total)
        except BaseException as exc:
            logger.exception("轉換迴圈發生未預期錯誤: %s", exc)

        elapsed = time.time() - start_time
        time_str = str(datetime.timedelta(seconds=int(elapsed)))

        if self._was_cancelled:
            logger.warning("轉換已停止 | 成功=%d | 失敗=%d", success, fail)
        else:
            logger.log(SUCCESS, "轉換完成 | 成功=%d | 失敗=%d | 耗時=%s",
                       success, fail, time_str)

        self.is_running = False
        self._emit_completed(time_str, self._was_cancelled)
