"""
filters.py - 向量過濾器 (優化版)


優化重點:
1. 合併重複邏輯,減少代碼重複
2. 改進向量化操作效能
3. 更清晰的函數結構
"""

from __future__ import annotations

from typing import Literal, Tuple

import numpy as np


def _local_stats_nan(
    u: np.ndarray,
    size: int,
    compute_median: bool = True,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    計算局部統計量 (Mean, Std, [Median]),忽略 NaN
    使用 Strided View 技術實現高效計算

    優化:
    - 確保記憶體連續性
    - 使用單一警告上下文
    - 預先分配結果陣列
    - compute_median=False 時略過 nanmedian（開銷最高的運算），
      適用於只需 mean/std 的過濾器（如 filter_vecstd）

    Parameters
    ----------
    compute_median : bool
        是否計算 median。設為 False 時回傳 None，
        可避免不必要的 nanmedian 計算開銷。
    """
    u = np.ascontiguousarray(u)

    pad_size = size // 2
    u_padded = np.pad(u, pad_size, mode="constant", constant_values=np.nan)

    # Sliding window view via stride tricks
    shape = u.shape + (size, size)
    strides = u_padded.strides + u_padded.strides
    windows = np.lib.stride_tricks.as_strided(u_padded, shape=shape, strides=strides)

    # Flatten window dimensions for nanmean/nanstd/nanmedian
    windows = windows.reshape(u.shape + (size * size,))

    with np.errstate(invalid="ignore"):
        mean_map = np.nanmean(windows, axis=2)
        std_map = np.nanstd(windows, axis=2)
        median_map = np.nanmedian(windows, axis=2) if compute_median else None

    return mean_map, std_map, median_map


def func_hist_filter(
    u: np.ndarray, std_limit: float = 2.0,
) -> Tuple[float, float, float]:
    """
    [保留相容] 計算過濾後的統計量

    優化: 提前返回邊界情況
    """
    valid_data = u[~np.isnan(u)]

    if len(valid_data) == 0:
        return (np.nan, np.nan, np.nan)

    f_mean = np.mean(valid_data)
    f_std = np.std(valid_data)

    mask = np.abs(valid_data - f_mean) <= std_limit * f_std
    filtered = valid_data[mask]

    if len(filtered) == 0:
        return (f_mean, f_std, np.median(valid_data))

    return (np.mean(filtered), np.std(filtered), np.median(filtered))


def _filter_deviation(
    ui: np.ndarray,
    vec_std: float,
    stat_type: Literal["median", "mean"] = "median",
) -> Tuple[np.ndarray, bool]:
    """
    通用偏差過濾器 (合併 filter_median 和 filter_vecstd 的共用邏輯)

    參數:
        ui: 輸入向量場
        vec_std: 標準差倍數閾值
        stat_type: 使用 "median" 或 "mean" 作為參考值

    優化:
    - 合併重複代碼
    - 減少條件分支
    - stat_type="mean" 時略過 nanmedian 計算（Phase 4A）
    """
    ERR_STD = 0.25
    u_copy = ui.copy()

    needs_median = stat_type == "median"
    f_mean, f_std, f_med = _local_stats_nan(u_copy, 3, compute_median=needs_median)

    reference = f_med if stat_type == "median" else f_mean

    std_limit = np.maximum(vec_std * f_std, ERR_STD)
    deviation = np.abs(u_copy - reference)

    mask = (deviation > std_limit) & (~np.isnan(u_copy))

    if np.any(mask):
        u_copy[mask] = np.nan
        return u_copy, True

    return u_copy, False


def filter_median(
    ui: np.ndarray, vec_std: float = 2.5,
) -> Tuple[np.ndarray, bool]:
    """
    中值偏差過濾器 (Vectorized)
    使用固定 3x3 鄰域進行快速過濾

    優化: 使用通用函數減少代碼重複
    """
    return _filter_deviation(ui, vec_std, stat_type="median")


def filter_vecstd(
    ui: np.ndarray, vec_std: float = 3.0,
) -> Tuple[np.ndarray, bool]:
    """
    標準差過濾器 (Vectorized)

    優化: 使用通用函數減少代碼重複
    """
    return _filter_deviation(ui, vec_std, stat_type="mean")


def filter_global(
    ui: np.ndarray, vi: np.ndarray, r_mm: float = 3.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    全域過濾器 (Vectorized)

    優化:
    - 提前返回邊界情況
    - 避免不必要的平方根計算
    - 預先計算常用值
    """
    uo = ui.copy()
    vo = vi.copy()

    valid_mask = ~np.isnan(uo) & ~np.isnan(vo)

    if not np.any(valid_mask):
        return uo, vo

    u_valid = uo[valid_mask]
    v_valid = vo[valid_mask]

    u_mean = np.mean(u_valid)
    v_mean = np.mean(v_valid)
    u_std = np.std(u_valid)
    v_std = np.std(v_valid)

    u_std_total = np.sqrt(u_std**2 + v_std**2) + 1e-10

    dist_sq = (uo - u_mean) ** 2 + (vo - v_mean) ** 2
    r_sq = dist_sq / u_std_total**2

    outlier_mask = r_sq >= r_mm**2

    uo[outlier_mask] = np.nan
    vo[outlier_mask] = np.nan

    return uo, vo
