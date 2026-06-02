"""
postprocess.py - PIV 後處理流程


整合過濾、插值、平滑的完整後處理流程
"""

import numpy as np
from typing import Dict, Tuple
from .filters import filter_median, filter_vecstd, filter_global
from .interpolation import interp_linear, interp_spline, interp_nan
from .smooth import func_smooth
# 注意：inpaint_nans 在函數內部延遲 import 以避免循環引用


def post_process(
    u: np.ndarray,
    v: np.ndarray,
    settings: Dict,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    PIV 後處理流程

    Parameters
    ----------
    u, v : np.ndarray
        原始速度分量
    settings : Dict
        後處理設定 (對應 a3)
        - uMin, uMax, vMin, vMax: 速度限制
        - thresStd: 標準差閾值 (-1=關閉)
        - thresMedian: 中值閾值 (-1=關閉)
        - thresGlobal: 全域閾值 (-1=關閉)
        - interpMethod: 插值方法 (-1=關閉, 1=Linear, 2=Cubic, 3=Kriging)
        - smoothData: 是否平滑

    Returns
    -------
    u_raw, v_raw : np.ndarray
        原始資料
    u_filt, v_filt : np.ndarray
        過濾後資料
    u_interp, v_interp : np.ndarray
        插值後資料
    u_smooth, v_smooth : np.ndarray
        平滑後資料
    """
    # 保存原始資料
    u_raw = u.copy()
    v_raw = v.copy()

    # 記錄原始 NaN 位置
    ng_orig = np.isnan(u) | np.isnan(v)

    # 過濾開始
    u_filt = u.copy()
    v_filt = v.copy()

    # 速度限制檢查 (
    # 注意： 使用 abs(u) 與限制值比較
    u_min = settings.get("u_min", -64)
    u_max = settings.get("u_max", 64)
    v_min = settings.get("v_min", -64)
    v_max = settings.get("v_max", 64)

    # 修正： 檢查的是 abs(u) < uMin 或 abs(u) > uMax
    # 這意味著如果 uMin=0，則檢查速度是否太小
    # 如果 uMin<0，則檢查 u_filt < uMin (不取 abs)
    # 修正：使用帶符號的邊界檢查 (Box filter)，符合 config 預設值 (-64, 64)
    # 原始  使用 abs(u) < min | abs(u) > max 是針對 Magnitude Limit
    # 但 pyCCV config 預設 -64/64 暗示 Signed Limit

    if settings.get("enable_vel_limit", True):
        invalid_vel = (
            (u_filt < u_min) |
            (u_filt > u_max) |
            (v_filt < v_min) |
            (v_filt > v_max)
        )
    else:
        invalid_vel = np.zeros_like(u_filt, dtype=bool)

    u_filt[invalid_vel] = np.nan
    v_filt[invalid_vel] = np.nan

    # 標準差過濾 (
    thres_std = settings.get("thres_std", 3.0)
    if thres_std > 0:
        u_filt, _ = filter_vecstd(u_filt, thres_std)
        v_filt, _ = filter_vecstd(v_filt, thres_std)
        # 保持一致性 (
        # u_filt = u_filt - v_filt*0 這行是為了讓 u 和 v 的 NaN 位置一致
        combined_nan = np.isnan(u_filt) | np.isnan(v_filt)
        u_filt[combined_nan] = np.nan
        v_filt[combined_nan] = np.nan

    # 全域過濾 (
    thres_global = settings.get("thres_global", -1)
    if thres_global > 0:
        u_filt, v_filt = filter_global(u_filt, v_filt, thres_global)

    # 中值過濾 (
    thres_median = settings.get("thres_median", 2.5)
    if thres_median > 0:
        u_filt, _ = filter_median(u_filt, thres_median)
        v_filt, _ = filter_median(v_filt, thres_median)
        # 保持一致性
        combined_nan = np.isnan(u_filt) | np.isnan(v_filt)
        u_filt[combined_nan] = np.nan
        v_filt[combined_nan] = np.nan

    # 插值 (
    interp_method = settings.get("interp_method", 2)
    if interp_method == 1:  # Linear
        u_interp = interp_linear(u_filt)
        v_interp = interp_linear(v_filt)
    elif interp_method == 2:  # Cubic spline
        u_interp = interp_spline(u_filt)
        v_interp = interp_spline(v_filt)
    else:
        u_interp = u_filt.copy()
        v_interp = v_filt.copy()

    # 平滑 (
    smooth_data = settings.get("smooth_data", True)
    if smooth_data:
        # 先處理連續 NaN (
        u_interp_smooth = interp_nan(u_interp)
        v_interp_smooth = interp_nan(v_interp)

        # 加權平滑 (
        u_smooth = func_smooth(u_interp_smooth)
        v_smooth = func_smooth(v_interp_smooth)

        # 恢復原始 NaN 位置
        ng_mask = ng_orig | invalid_vel
        u_smooth[ng_mask] = np.nan
        v_smooth[ng_mask] = np.nan
    else:
        u_smooth = u_interp.copy()
        v_smooth = v_interp.copy()

    return u_raw, v_raw, u_filt, v_filt, u_interp, v_interp, u_smooth, v_smooth


def piv_lab_post_proc(
    u: np.ndarray,
    v: np.ndarray,
    caluv: float = 1.0,
    valid_vel: list = None,
    do_stdev_check: bool = True,
    std_thresh: float = 4.0,
    do_local_median: bool = True,
    neigh_thresh: float = 1.5
) -> Tuple[np.ndarray, np.ndarray]:
    """
    pyCCV 內部後處理 (用於 multi-pass 之間)


    Parameters
    ----------
    u, v : np.ndarray
        速度分量
    caluv : float
        pixel-to-physical 校正係數
    valid_vel : list
        [umin, umax, vmin, vmax] 速度限制
    do_stdev_check : bool
        是否進行標準差檢查
    std_thresh : float
        標準差閾值
    do_local_median : bool
        是否進行局部中值檢查
    neigh_thresh : float
        鄰域閾值

    Returns
    -------
    u_out, v_out : np.ndarray
        處理後的速度分量
    """
    from scipy import ndimage
    from .piv_fft import inpaint_nans  # 延遲 import 避免循環引用

    u_out = u.copy()
    v_out = v.copy()

    # 速度限制 (
    if valid_vel is not None and len(valid_vel) == 4:
        u_min_val, u_max_val, v_min_val, v_max_val = valid_vel

        # 分別檢查 u 和 v 的限制
        u_out[(u_out * caluv < u_min_val) | (u_out * caluv > u_max_val)] = np.nan
        v_out[(v_out * caluv < v_min_val) | (v_out * caluv > v_max_val)] = np.nan

        # 統一 NaN 位置 (保持一致性)
        combined_nan = np.isnan(u_out) | np.isnan(v_out)
        u_out[combined_nan] = np.nan
        v_out[combined_nan] = np.nan

    # 局部中值檢查 (
    if do_local_median:
        neigh_filt = ndimage.median_filter(u_out, size=3, mode='reflect')
        neigh_filt = inpaint_nans(neigh_filt, method=4)
        deviation = np.abs(neigh_filt - u_out)
        u_out[deviation > neigh_thresh] = np.nan

        neigh_filt = ndimage.median_filter(v_out, size=3, mode='reflect')
        neigh_filt = inpaint_nans(neigh_filt, method=4)
        deviation = np.abs(neigh_filt - v_out)
        v_out[deviation > neigh_thresh] = np.nan

    # 標準差檢查 (
    if do_stdev_check:
        mean_u = np.nanmean(u_out)
        mean_v = np.nanmean(v_out)
        std_u = np.nanstd(u_out)
        std_v = np.nanstd(v_out)

        min_val_u = mean_u - std_thresh * std_u
        max_val_u = mean_u + std_thresh * std_u
        min_val_v = mean_v - std_thresh * std_v
        max_val_v = mean_v + std_thresh * std_v

        u_out[u_out < min_val_u] = np.nan
        u_out[u_out > max_val_u] = np.nan
        v_out[v_out < min_val_v] = np.nan
        v_out[v_out > max_val_v] = np.nan

    # 保持一致性 (
    u_out[np.isnan(v_out)] = np.nan
    v_out[np.isnan(u_out)] = np.nan

    return u_out, v_out
