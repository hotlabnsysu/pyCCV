from pathlib import Path
from typing import Any, Dict

import numpy as np

from services.logger import logger
from shared.io_formats import load_flo as _load_flo_shared
from shared.io_formats import load_raw_custom as _load_raw_shared
from shared.io_formats import save_flo as _save_flo_shared
from shared.io_formats import save_mat as _save_mat_shared
from shared.io_formats import save_npz as _save_npz_shared
from shared.io_formats import save_raw_custom as _save_raw_shared


def save_result(path: Path, data: Dict[str, Any], fmt: str = "flo") -> None:
    """將 PIV 結果儲存為指定格式。"""
    save_path = path.with_suffix(f".{fmt}")

    try:
        if fmt == "flo":
            _save_flo_shared(save_path, data)
        elif fmt == "npz":
            _save_npz_shared(save_path, data)
        elif fmt == "mat":
            try:
                _save_mat_shared(save_path, data)
            except ImportError:
                logger.warning("scipy 未安裝，回退至 .flo 輸出")
                save_result(path, data, "flo")
                return
        elif fmt == "raw":
            _save_raw_shared(save_path, data)
        else:
            save_result(path, data, "flo")
            return
    except OSError as exc:
        logger.error("儲存失敗 (磁碟錯誤) | 檔案=%s | 原因=%s", save_path.name, exc)
        try:
            if save_path.exists():
                save_path.unlink()
        except OSError:
            pass
        raise
    except ValueError as exc:
        logger.warning("儲存失敗 (資料錯誤) | 檔案=%s | 原因=%s", save_path.name, exc)


def load_raw_result(path: Path) -> Dict[str, np.ndarray]:
    """讀取自訂 RAW 格式。"""
    return _load_raw_shared(path)


def load_flo(path: Path) -> Dict[str, np.ndarray]:
    """讀取 Middlebury .flo 格式。"""
    return _load_flo_shared(path)

