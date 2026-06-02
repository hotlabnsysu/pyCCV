
from concurrent.futures import CancelledError
from concurrent.futures.process import BrokenProcessPool
import os
import queue
import threading
import time
import datetime
import numpy as np
import scipy.fft
from PIL import Image
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

from PySide6.QtCore import QObject, Signal, QThread

from core import piv_fft_multi, piv_fft_multi_parallel, post_process
from utils import save_result
from .logger import logger, SUCCESS


def _process_pair_worker(args):
    """Top-level function for ProcessPoolExecutor (must be picklable).

    Returns ``(idx, skipped, x, y, results, file_path_str, error_msg)``.
    Any exception inside the worker is caught and surfaced via ``error_msg``
    so a single bad pair cannot kill the worker process and silently turn the
    whole batch into a fake completion.
    """
    idx, p1, p2, piv_opts, post_opts, enabled_exports, out_root, output_fmt, output_ext, force_overwrite, invert_gray = args
    try:
        p1, p2 = Path(p1), Path(p2)

        stem = p1.stem
        source_folder_name = p1.parent.name

        current_exports = []
        for suffix, stage in enabled_exports:
            folder_path = out_root / f"{source_folder_name}{suffix}"
            folder_path.mkdir(parents=True, exist_ok=True)
            current_exports.append((folder_path, stage))

        if not force_overwrite:
            if should_skip_existing_outputs(current_exports, stem, output_ext):
                return idx, True, None, None, None, str(p1), None

        with Image.open(p1) as img:
            img1 = np.array(img.convert("I;16") if img.mode.startswith("I") or img.mode == "F" else img.convert("L"))
        with Image.open(p2) as img:
            img2 = np.array(img.convert("I;16") if img.mode.startswith("I") or img.mode == "F" else img.convert("L"))

        if invert_gray:
            max_val = np.iinfo(img1.dtype).max
            img1 = max_val - img1
            img2 = max_val - img2

        x, y, u, v, _ = piv_fft_multi(img1, img2, **piv_opts)
        del img2

        u_raw, v_raw, u_filt, v_filt, u_interp, v_interp, u_smooth, v_smooth = post_process(u, v, post_opts)

        stage_vectors = {
            "raw": {"u": u_raw, "v": v_raw},
            "filt": {"u": u_filt, "v": v_filt},
            "interp": {"u": u_interp, "v": v_interp},
            "smooth": {"u": u_smooth, "v": v_smooth},
        }
        for folder_path, stage in current_exports:
            save_data = {"x": x, "y": y}
            save_data.update(stage_vectors.get(stage, {}))
            save_result(folder_path / stem, save_data, fmt=output_fmt)

        results = {
            "u_raw": u_raw, "v_raw": v_raw,
            "u_filt": u_filt, "v_filt": v_filt,
            "u_interp": u_interp, "v_interp": v_interp,
            "u_smooth": u_smooth, "v_smooth": v_smooth,
            "u_final": u_smooth, "v_final": v_smooth,
        }
        return idx, False, x, y, results, str(p1), None
    except BaseException as exc:
        return idx, False, None, None, None, str(p1), f"{type(exc).__name__}: {exc}"


def should_skip_existing_outputs(current_exports, stem, output_ext) -> bool:
    """Return True only when every requested export for a stem already exists."""
    if not current_exports:
        return False
    return all((folder_path / f"{stem}{output_ext}").exists() for folder_path, _ in current_exports)


def build_export_plan(image_pairs, basic_opts, output_dir):
    has_output_options = any(
        basic_opts.get(option, False)
        for option in ("export_raw", "export_filt", "export_interp", "export_smooth")
    )
    if not has_output_options or not output_dir:
        return {
            "has_output_options": has_output_options,
            "suffixes": [],
            "export_folders": [],
            "existing_folders": [],
        }

    out_root = Path(output_dir)
    source_folders = {p1.parent.name for p1, _ in image_pairs}

    suffixes = []
    if basic_opts.get("export_raw", False):
        suffixes.append("_Raw")
    if basic_opts.get("export_filt", False):
        suffixes.append("_Filt")
    if basic_opts.get("export_interp", False):
        suffixes.append("_Interp")
    if basic_opts.get("export_smooth", False):
        suffixes.append("_Smooth")

    export_folders = [
        out_root / f"{folder_name}{suffix}"
        for folder_name in source_folders
        for suffix in suffixes
    ]
    existing_folders = [folder for folder in export_folders if folder.exists()]
    return {
        "has_output_options": has_output_options,
        "suffixes": suffixes,
        "export_folders": export_folders,
        "existing_folders": existing_folders,
    }


class AnalysisWorker(QObject):
    """分析工作執行緒物件，透過 Qt Signal 回報進度與結果"""

    progress = Signal(int, int, float)          # current, total, remaining_sec
    result = Signal(object, object, object, object, object)  # x, y, results, img, path
    completed = Signal(str, bool)               # time_str, was_cancelled
    pair_error = Signal(int, str, str)          # pair_idx, filename, error_msg

    def __init__(self, service: "AnalysisService"):
        super().__init__()
        self._service = service

    def run(self):
        """QThread 的 run 入口，由 AnalysisService 呼叫"""
        svc = self._service
        svc._analysis_loop()


class AnalysisService(QObject):
    """PIV 分析服務，封裝計算邏輯並透過 Qt Signal 跨執行緒回報狀態"""

    # Public signals (forwarded from worker)
    progress = Signal(int, int, float)
    result = Signal(object, object, object, object, object)
    completed = Signal(str, bool)
    pair_error = Signal(int, str, str)  # pair_idx, filename, error_msg

    def __init__(self, max_workers: int = 4):
        super().__init__()
        self.max_workers = max_workers
        self.is_running = False
        self.is_paused = False
        self._shutdown = False
        self._was_cancelled = False
        self._cancel_event = threading.Event()
        self._resume_event = threading.Event()
        self._resume_event.set()

        # Analysis parameters (set before starting)
        self._image_pairs: List[Tuple[Path, Path]] = []
        self._settings: Dict = {}
        self._output_dir: str = ""
        self._force_overwrite: bool = False

        # Thread management
        self._thread: Optional[QThread] = None
        self._worker: Optional[AnalysisWorker] = None

    def get_image_pairs(self, input_dir: str, range_limit: int = 0) -> List[Tuple[Path, Path]]:
        """
        Get list of image pairs from directory.

        支援搜尋上層目錄下的所有子資料夾
        支援混合多種影像格式
        優先順序：
        1. 先嘗試在輸入目錄本身搜尋影像
        2. 如果沒有，搜尋子資料夾中的影像
        """
        from config import SUPPORTED_IMAGE_FORMATS

        input_path = Path(input_dir)
        supported_exts = {fmt.lower() for fmt in SUPPORTED_IMAGE_FORMATS}

        all_files = [
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in supported_exts
        ]

        if all_files:
            files = sorted(all_files)
            pairs = self._make_pairs_from_files(files, range_limit)
            return [(Path(p1), Path(p2)) for p1, p2 in pairs]

        subdir_files = {}
        for subdir in input_path.iterdir():
            if not subdir.is_dir():
                continue
            files = [
                f for f in subdir.iterdir()
                if f.is_file() and f.suffix.lower() in supported_exts
            ]
            if files:
                subdir_files[subdir] = files

        if subdir_files:
            all_pairs = []
            for subdir in sorted(subdir_files.keys()):
                files = sorted(subdir_files[subdir])
                if files:
                    pairs = self._make_pairs_from_files(files, range_limit)
                    all_pairs.extend([(Path(p1), Path(p2)) for p1, p2 in pairs])
            return all_pairs

        return []

    def _make_pairs_from_files(self, files: List[Path], range_limit) -> List[Tuple[str, str]]:
        """從檔案列表建立影像對"""
        if not files:
            return []

        if range_limit == 0:
            start, end = 0, len(files) - 1
        elif isinstance(range_limit, int):
            start, end = range_limit - 1, range_limit
        elif isinstance(range_limit, list) and len(range_limit) == 2:
            start, end = range_limit[0] - 1, range_limit[1] - 1
        else:
            start, end = 0, len(files) - 1

        pairs = []
        for i in range(start, min(end, len(files) - 1)):
            pairs.append((str(files[i]), str(files[i + 1])))

        return pairs

    def run_analysis(self,
                     image_pairs: List[Tuple[Path, Path]],
                     settings: Dict,
                     output_dir: str,
                     force_overwrite: bool = False):
        """
        Start analysis on a list of image pairs (non-blocking, runs in a QThread).
        Progress/results are delivered via Qt Signals.
        """
        if self.is_running:
            logger.warning("分析已在執行中")
            return

        self.is_running = True
        self.is_paused = False
        self._shutdown = False
        self._was_cancelled = False
        self._cancel_event.clear()
        self._resume_event.set()
        self._image_pairs = image_pairs
        self._settings = settings
        self._output_dir = output_dir
        self._force_overwrite = force_overwrite

        # Clean up previous run's thread/worker
        if self._worker is not None:
            try:
                self._worker.progress.disconnect()
                self._worker.result.disconnect()
                self._worker.completed.disconnect()
                self._worker.pair_error.disconnect()
            except (RuntimeError, TypeError):
                pass
            self._worker.deleteLater()
            self._worker = None
        if self._thread is not None:
            if self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(1000)
            self._thread.deleteLater()
            self._thread = None

        self._worker = AnalysisWorker(self)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        # Wire worker signals -> service signals (queued, cross-thread safe)
        self._worker.progress.connect(self.progress)
        self._worker.result.connect(self.result)
        self._worker.completed.connect(self.completed)
        self._worker.pair_error.connect(self.pair_error)

        self._thread.started.connect(self._worker.run)
        self._thread.start()

    def stop(self):
        """Stop the analysis"""
        self.is_running = False
        self._shutdown = True
        self._was_cancelled = True
        self._cancel_event.set()
        self._resume_event.set()
        logger.debug("收到停止分析請求")

    def shutdown(self):
        """Shutdown background thread resources."""
        self.stop()
        if self._thread and self._thread.isRunning():
            self._thread.quit()
            if not self._thread.wait(5000):
                logger.warning("分析執行緒未能在 5 秒內結束，強制終止")
                self._thread.terminate()
                self._thread.wait(1000)

    def pause(self):
        """Pause the analysis"""
        self.is_paused = True
        self._resume_event.clear()
        logger.debug("分析已暫停")

    def resume(self):
        """Resume the analysis"""
        self.is_paused = False
        self._resume_event.set()
        logger.debug("分析已繼續")

    # ------------------------------------------------------------------
    # Internal computation (runs inside QThread)
    # ------------------------------------------------------------------

    def _load_single_image(self, path):
        with Image.open(path) as img:
            if img.mode.startswith("I") or img.mode == "F":
                return np.array(img.convert("I;16"))
            return np.array(img.convert("L"))

    def _sliding_image_pairs(self, pairs):
        if not pairs:
            return

        cached_img2_path = None
        cached_img2_data = None

        for paths in pairs:
            p1, p2 = paths

            try:
                if cached_img2_path is not None and cached_img2_path == p1:
                    img1 = cached_img2_data
                else:
                    img1 = self._load_single_image(p1)

                img2 = self._load_single_image(p2)

                cached_img2_path = p2
                cached_img2_data = img2

                yield (paths, (img1, img2))

                img1 = None

            except Exception as e:
                cached_img2_path = None
                cached_img2_data = None
                yield (paths, e)

    def _emit_progress(self, current, total, remaining):
        """Emit progress signal via the worker (so it crosses the thread boundary properly)"""
        if self._worker:
            self._worker.progress.emit(current, total, remaining)

    def _emit_result(self, x, y, results, img, path):
        if self._worker:
            self._worker.result.emit(x, y, results, img, path)

    def _emit_completed(self, time_str, cancelled):
        if self._worker:
            self._worker.completed.emit(time_str, cancelled)

    def _emit_pair_error(self, pair_idx, filename, error_msg):
        if self._worker:
            self._worker.pair_error.emit(pair_idx, filename, error_msg)

    def _build_current_exports(self, enabled_exports, out_root: Path, source_folder_name: str):
        current_exports = []
        for suffix, stage in enabled_exports:
            folder_path = out_root / f"{source_folder_name}{suffix}"
            folder_path.mkdir(parents=True, exist_ok=True)
            current_exports.append((folder_path, stage))
        return current_exports

    def _build_solver_options(self, piv_opts: Dict[str, Any]):
        run_opts = piv_opts.copy()
        if "overlap" in run_opts:
            overlap = run_opts.pop("overlap")
            int_area_1 = run_opts.get("int_area_1", 64)
            run_opts["step"] = max(1, int(int_area_1 * (1.0 - overlap)))
        if "corr_style" in run_opts:
            del run_opts["corr_style"]

        valid_args = [
            "int_area_1",
            "step",
            "int_area_2",
            "int_area_3",
            "int_area_4",
            "int_area_5",
            "int_area_6",
            "num_passes",
            "sub_pix_method",
            "mask",
            "roi",
            "window_deform",
            "repeat_corr",
            "disable_autocorr",
            "do_pad",
        ]
        filtered_opts = {key: value for key, value in run_opts.items() if key in valid_args}
        for key in ["int_area_1", "int_area_2", "int_area_3", "int_area_4", "int_area_5", "int_area_6"]:
            if key in filtered_opts and filtered_opts[key] == "none":
                filtered_opts[key] = 16
        return filtered_opts

    def _save_stage_outputs(self, current_exports, stem, x, y, stage_vectors, output_fmt):
        for folder_path, stage in current_exports:
            save_stem = folder_path / stem
            save_data = {"x": x, "y": y}
            save_data.update(stage_vectors.get(stage, {}))
            save_result(save_stem, save_data, fmt=output_fmt)

    def _build_results_payload(self, u_raw, v_raw, u_filt, v_filt, u_interp, v_interp, u_smooth, v_smooth):
        return {
            "u_raw": u_raw,
            "v_raw": v_raw,
            "u_filt": u_filt,
            "v_filt": v_filt,
            "u_interp": u_interp,
            "v_interp": v_interp,
            "u_smooth": u_smooth,
            "v_smooth": v_smooth,
            "u_final": u_smooth,
            "v_final": v_smooth,
        }

    def _analysis_loop(self):
        image_pairs = self._image_pairs
        settings = self._settings
        output_dir = self._output_dir
        force_overwrite = self._force_overwrite

        total_pairs = len(image_pairs)
        start_time = time.time()

        try:
            out_root = Path(output_dir)
            out_root.mkdir(parents=True, exist_ok=True)

            export_configs = [
                ("export_raw", "_Raw", "raw"),
                ("export_filt", "_Filt", "filt"),
                ("export_interp", "_Interp", "interp"),
                ("export_smooth", "_Smooth", "smooth")
            ]

            piv_opts = settings.get("piv", {})
            post_opts = settings.get("postproc", {})
            basic_opts = settings.get("basic", {})

            enabled_exports = []
            for opt_key, suffix, stage in export_configs:
                if basic_opts.get(opt_key, False):
                    enabled_exports.append((suffix, stage))

            output_fmt = basic_opts.get("output_format", "flo")
            ext_map = {"flo": ".flo", "npz": ".npz", "raw": ".raw", "mat": ".mat"}
            output_ext = ext_map.get(output_fmt, ".flo")

            if enabled_exports and force_overwrite:
                clean_exts = {".flo", ".npz", ".raw", ".mat"}
                source_folders = {p1.parent.name for p1, _ in image_pairs}
                for source_folder_name in source_folders:
                    for suffix, _ in enabled_exports:
                        folder_path = out_root / f"{source_folder_name}{suffix}"
                        folder_path.mkdir(parents=True, exist_ok=True)
                        for existing_file in folder_path.iterdir():
                            if existing_file.is_file() and existing_file.suffix.lower() in clean_exts:
                                try:
                                    existing_file.unlink()
                                except Exception as e:
                                    logger.warning("移除舊檔失敗 | 檔案=%s | 原因=%s", existing_file, e)

            compute_mode = basic_opts.get("compute_mode", "cpu")
            num_workers = basic_opts.get("num_workers", 4)
            try:
                num_workers = int(num_workers) if num_workers else 1
            except (TypeError, ValueError):
                num_workers = 1
            num_workers = max(1, num_workers)

            # FFT-level parallelism: scipy.fft releases the GIL and accepts a
            # global worker pool — apply it in *all* compute modes so the default
            # cpu mode also benefits on multicore machines.
            fft_workers = max(1, min(num_workers, os.cpu_count() or 1))
            with scipy.fft.set_workers(fft_workers):
                self._run_pairs(
                    image_pairs=image_pairs,
                    total_pairs=total_pairs,
                    start_time=start_time,
                    out_root=out_root,
                    enabled_exports=enabled_exports,
                    output_fmt=output_fmt,
                    output_ext=output_ext,
                    force_overwrite=force_overwrite,
                    piv_opts=piv_opts,
                    post_opts=post_opts,
                    compute_mode=compute_mode,
                    num_workers=num_workers,
                )

        except Exception:
            logger.exception("分析迴圈發生未預期錯誤")
            self._was_cancelled = True
        finally:
            end_time = time.time()
            total_time_seconds = end_time - start_time
            total_time_str = str(datetime.timedelta(seconds=int(total_time_seconds)))

            self.is_running = False
            if self._was_cancelled:
                logger.warning("分析已取消 | 耗時=%s", total_time_str)
            else:
                logger.log(SUCCESS, "分析完成 | 耗時=%s", total_time_str)

            self._emit_completed(total_time_str, self._was_cancelled)

            if self._thread:
                self._thread.quit()

    def _run_pairs(self, *, image_pairs, total_pairs, start_time, out_root,
                    enabled_exports, output_fmt, output_ext, force_overwrite,
                    piv_opts, post_opts, compute_mode, num_workers):
        """Dispatch to parallel-process or sequential path depending on mode."""
        use_pair_parallel = (compute_mode == "cpu_parallel" and num_workers > 1 and total_pairs > 1)

        if use_pair_parallel:
            logger.info("啟動 CPU 平行模式 (ProcessPool) | 工作核心=%d", num_workers)
            self._run_pairs_parallel(
                image_pairs=image_pairs,
                total_pairs=total_pairs,
                start_time=start_time,
                out_root=out_root,
                enabled_exports=enabled_exports,
                output_fmt=output_fmt,
                output_ext=output_ext,
                force_overwrite=force_overwrite,
                piv_opts=piv_opts,
                post_opts=post_opts,
                num_workers=num_workers,
            )
            return

        if compute_mode == "cpu_parallel" and num_workers > 1:
            piv_solver = lambda a, b, **opts: piv_fft_multi_parallel(a, b, num_workers=num_workers, **opts)
            logger.info("啟動 CPU FFT 平行模式 | 工作核心=%d", num_workers)
        else:
            piv_solver = piv_fft_multi
            logger.info("啟動 CPU 傳統模式 (單行程循序)")

        self._run_pairs_sequential(
            image_pairs=image_pairs,
            total_pairs=total_pairs,
            start_time=start_time,
            out_root=out_root,
            enabled_exports=enabled_exports,
            output_fmt=output_fmt,
            output_ext=output_ext,
            force_overwrite=force_overwrite,
            piv_opts=piv_opts,
            post_opts=post_opts,
            piv_solver=piv_solver,
        )

    def _run_pairs_parallel(self, *, image_pairs, total_pairs, start_time, out_root,
                              enabled_exports, output_fmt, output_ext, force_overwrite,
                              piv_opts, post_opts, num_workers):
        from concurrent.futures import ProcessPoolExecutor, as_completed

        # Hoist solver-options out of the per-pair loop — they don't change per pair.
        filtered_opts = self._build_solver_options(piv_opts)
        invert_gray = piv_opts.get("invert_gray", False)

        worker_args = [
            (i, str(p1), str(p2), filtered_opts, post_opts,
             enabled_exports, out_root, output_fmt, output_ext,
             force_overwrite, invert_gray)
            for i, (p1, p2) in enumerate(image_pairs)
        ]

        completed_count = 0
        broken_pool = False

        # Throttle live-preview emits to ~10 Hz: ProcessPool finishes pairs much
        # faster than matplotlib can redraw, so emitting every result floods
        # the Qt event queue and the GUI keeps "replaying" frames after the
        # analysis is done. Disk saves are unaffected — those happen inside
        # the worker process for every pair.
        PREVIEW_MIN_INTERVAL = 0.1
        last_preview_emit = 0.0

        with ProcessPoolExecutor(max_workers=num_workers) as pool:
            futures = {
                pool.submit(_process_pair_worker, args): args
                for args in worker_args
            }

            for future in as_completed(futures):
                while not self._resume_event.wait(timeout=0.5):
                    if self._shutdown:
                        break
                if self._shutdown:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break

                args = futures[future]
                pair_idx = args[0]
                pair_path = Path(args[1])
                try:
                    idx, skipped, x, y, results, file_path_str, error_msg = future.result()
                    if error_msg:
                        # Worker caught an exception — surface it and continue.
                        self._emit_pair_error(pair_idx, pair_path.name, error_msg)
                        logger.error("處理影像對失敗 (worker) | %s | %s", pair_path.name, error_msg)
                    elif not skipped and results is not None:
                        # Always emit the final pair so the user sees the last
                        # state; otherwise drop frames the GUI cannot keep up
                        # with.
                        is_last_pair = (completed_count + 1) >= total_pairs
                        now = time.time()
                        if is_last_pair or (now - last_preview_emit) >= PREVIEW_MIN_INTERVAL:
                            try:
                                preview_img = self._load_single_image(Path(file_path_str))
                            except Exception as load_exc:
                                logger.debug("預覽影像載入失敗 (略過) | %s | %s",
                                             pair_path.name, load_exc)
                                preview_img = None
                            self._emit_result(x, y, results, preview_img, Path(file_path_str))
                            last_preview_emit = now
                except BrokenProcessPool as e:
                    broken_pool = True
                    self._emit_pair_error(pair_idx, pair_path.name,
                                          f"ProcessPool 已中斷 (worker process 異常結束): {e}")
                    logger.error("ProcessPool 已中斷，剩餘任務取消")
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                except Exception as e:
                    self._emit_pair_error(pair_idx, pair_path.name, str(e))
                    logger.error("取得結果失敗 | idx=%d | 原因=%s", pair_idx, e)

                completed_count += 1
                elapsed = time.time() - start_time
                avg_time = elapsed / completed_count
                remaining = avg_time * (total_pairs - completed_count)
                self._emit_progress(completed_count, total_pairs, remaining)

        if broken_pool:
            self._was_cancelled = True

    def _run_pairs_sequential(self, *, image_pairs, total_pairs, start_time, out_root,
                                enabled_exports, output_fmt, output_ext, force_overwrite,
                                piv_opts, post_opts, piv_solver):
        # Hoist solver-options once: cancel_event reference is stable across pairs.
        filtered_opts = self._build_solver_options(piv_opts)
        filtered_opts["cancel_event"] = self._cancel_event
        invert_gray = piv_opts.get("invert_gray", False)

        io_queue = queue.Queue(maxsize=8)
        io_errors = []

        def _io_consumer():
            while True:
                task = io_queue.get()
                if task is None:
                    io_queue.task_done()
                    break
                try:
                    self._save_stage_outputs(*task)
                except OSError as e:
                    io_errors.append(e)
                    logger.error("I/O 錯誤: %s", e)
                io_queue.task_done()

        io_thread = threading.Thread(target=_io_consumer, daemon=True)
        io_thread.start()

        running_avg = 0.0

        for i, (paths, imgs_or_err) in enumerate(self._sliding_image_pairs(image_pairs)):
            p1, p2 = paths
            if self._shutdown:
                break
            if io_errors:
                logger.error("磁碟 I/O 錯誤，停止分析: %s", io_errors[0])
                self._shutdown = True
                break

            while not self._resume_event.wait(timeout=0.5):
                if self._shutdown:
                    break
            if self._shutdown:
                break

            pair_start = time.time()

            try:
                stem = p1.stem
                source_folder_name = p1.parent.name
                current_exports = self._build_current_exports(enabled_exports, out_root, source_folder_name)

                # Order matters: surface image-load errors *before* the skip
                # check, otherwise a corrupt image with stale outputs disappears
                # silently.
                if isinstance(imgs_or_err, Exception):
                    raise imgs_or_err

                if not force_overwrite and should_skip_existing_outputs(current_exports, stem, output_ext):
                    logger.debug("跳過 %s (輸出已存在)", stem)
                else:
                    img1, img2 = imgs_or_err

                    if invert_gray:
                        max_val = np.iinfo(img1.dtype).max
                        img1 = max_val - img1
                        img2 = max_val - img2

                    x, y, u, v, _ = piv_solver(img1, img2, **filtered_opts)

                    del img2

                    u_raw, v_raw, u_filt, v_filt, u_interp, v_interp, u_smooth, v_smooth = post_process(u, v, post_opts)

                    del u, v

                    # No defensive .copy(): the I/O consumer reads the arrays
                    # exactly once before the producer del's its references on
                    # the next iteration. The bounded queue (maxsize=8) provides
                    # back-pressure.
                    stage_vectors = {
                        "raw": {"u": u_raw, "v": v_raw},
                        "filt": {"u": u_filt, "v": v_filt},
                        "interp": {"u": u_interp, "v": v_interp},
                        "smooth": {"u": u_smooth, "v": v_smooth},
                    }
                    io_queue.put((current_exports, stem, x, y, stage_vectors, output_fmt))

                    results = self._build_results_payload(
                        u_raw, v_raw, u_filt, v_filt, u_interp, v_interp, u_smooth, v_smooth
                    )

                    self._emit_result(x, y, results, img1, p1)

            except CancelledError:
                logger.info("分析已被使用者取消 (FFT 中斷)")
                break
            except Exception as exc:
                logger.exception("處理影像對失敗 | 檔案=%s-%s", p1.name, p2.name)
                self._emit_pair_error(i, p1.name, str(exc))
            finally:
                pair_time = time.time() - pair_start
                processed = i + 1
                running_avg += (pair_time - running_avg) / processed
                remaining = running_avg * (total_pairs - processed)
                self._emit_progress(processed, total_pairs, remaining)

        io_queue.put(None)
        io_thread.join(timeout=30)
