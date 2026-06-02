"""
interpolation.py - NaN 向量插值方法 (優化版)


實作三種插值方法:
- 線性插值 (四鄰域平均)
- 三次樣條插值 (Stencil based)
- 連續 NaN 補償

優化重點:
1. 簡化邊界處理邏輯
2. 減少重複計算
3. 改進記憶體使用效率
"""

import numpy as np
from scipy import ndimage
from typing import Tuple


def interp_linear(ui: np.ndarray) -> np.ndarray:
    """
    線性插值 (Vectorized)
    使用卷積計算四鄰域平均

    優化:
    - 提前返回無 NaN 情況
    - 簡化邊界處理
    - 減少中間變數
    """
    uo = ui.copy()
    nan_mask = np.isnan(uo)

    # 提前返回:沒有 NaN
    if not np.any(nan_mask):
        return uo

    # 四鄰域核心
    kernel = np.array([[0, 1, 0],
                       [1, 0, 1],
                       [0, 1, 0]], dtype=np.float64)

    # 將 NaN 替換為 0 進行卷積
    u_filled = np.nan_to_num(uo, nan=0.0)
    valid_mask = (~nan_mask).astype(np.float64)

    # 計算鄰域和與鄰域數量
    neighbor_sum = ndimage.convolve(u_filled, kernel, mode='constant', cval=0.0)
    neighbor_count = ndimage.convolve(valid_mask, kernel, mode='constant', cval=0.0)

    # 計算平均值 (避免除零)
    with np.errstate(divide='ignore', invalid='ignore'):
        avg = neighbor_sum / neighbor_count

    # 只填充有鄰居的 NaN 位置
    fill_mask = nan_mask & (neighbor_count > 0)
    uo[fill_mask] = avg[fill_mask]

    # 邊界處理 - 使用與原始版本完全相同的邏輯
    # 注意:這裡使用卷積後仍為 NaN 的位置
    mx, my = uo.shape

    # Top edge (using row 1)
    mask_top = np.isnan(uo[:, 0]) & ~np.isnan(uo[:, 1])
    uo[mask_top, 0] = uo[mask_top, 1]

    # Bottom edge (using row -2)
    mask_btm = np.isnan(uo[:, -1]) & ~np.isnan(uo[:, -2])
    uo[mask_btm, -1] = uo[mask_btm, -2]

    # Left edge (using col 1)
    mask_left = np.isnan(uo[0, :]) & ~np.isnan(uo[1, :])
    uo[0, mask_left] = uo[1, mask_left]

    # Right edge (using col -2)
    mask_right = np.isnan(uo[-1, :]) & ~np.isnan(uo[-2, :])
    uo[-1, mask_right] = uo[-2, mask_right]

    # Corners (simple check)
    if np.isnan(uo[0, 0]) and not np.isnan(uo[1, 1]): uo[0, 0] = uo[1, 1]
    if np.isnan(uo[-1, 0]) and not np.isnan(uo[-2, 1]): uo[-1, 0] = uo[-2, 1]
    if np.isnan(uo[0, -1]) and not np.isnan(uo[1, -2]): uo[0, -1] = uo[1, -2]
    if np.isnan(uo[-1, -1]) and not np.isnan(uo[-2, -2]): uo[-1, -1] = uo[-2, -2]

    return uo


def interp_spline(ui: np.ndarray) -> np.ndarray:
    """
    三次樣條插值 (Vectorized)
    Stencil approach: 1/3 * (4-neighbors) - 1/12 * (4-far-neighbors)

    優化:
    - 簡化邏輯,移除冗長註解
    - 預先定義核心常數
    - 清晰的條件檢查
    """
    # 先用線性插值填充
    uo = interp_linear(ui)

    # 記錄原始 NaN 位置
    nan_mask = np.isnan(ui)

    # 提前返回:沒有 NaN
    if not np.any(nan_mask):
        return uo

    # 定義近鄰和遠鄰核心
    k_near = np.array([[0, 1, 0],
                       [1, 0, 1],
                       [0, 1, 0]], dtype=np.float64)

    k_far = np.zeros((5, 5), dtype=np.float64)
    k_far[0, 2] = k_far[4, 2] = k_far[2, 0] = k_far[2, 4] = 1.0

    # 計算原始資料的有效性和值
    valid_mask = (~np.isnan(ui)).astype(np.float64)
    u_filled = np.nan_to_num(ui, nan=0.0)

    # 計算鄰域統計
    count_near = ndimage.convolve(valid_mask, k_near, mode='constant', cval=0.0)
    count_far = ndimage.convolve(valid_mask, k_far, mode='constant', cval=0.0)
    sum_near = ndimage.convolve(u_filled, k_near, mode='constant', cval=0.0)
    sum_far = ndimage.convolve(u_filled, k_far, mode='constant', cval=0.0)

    # 樣條插值條件:近鄰和遠鄰都完整 (各 4 個)
    spline_mask = nan_mask & (count_near == 4) & (count_far == 4)

    # 應用樣條公式
    if np.any(spline_mask):
        spline_value = (sum_near - sum_far / 4.0) / 3.0
        uo[spline_mask] = spline_value[spline_mask]

    return uo


def interp_nan(ui: np.ndarray) -> np.ndarray:
    """
    連續 NaN 補償

    優化:
    - 只對 NaN 區域進行中值濾波
    - 減少不必要的陣列複製
    - 提前返回邊界情況
    """
    # 記錄原始 NaN 位置
    nan_mask = np.isnan(ui)

    # 提前返回:沒有 NaN
    if not np.any(nan_mask):
        return ui.copy()

    # 先用線性插值填充
    ut = interp_linear(ui)

    # 對於線性插值無法填充的區域,用全域平均值填充
    still_nan = np.isnan(ut)
    if np.any(still_nan):
        valid_mask = ~nan_mask
        if np.any(valid_mask):
            ut[still_nan] = np.mean(ui[valid_mask])
        else:
            ut[:] = 0.0

    # 中值平滑 (只對原始 NaN 區域)
    # 優化:先對整個陣列做中值濾波,然後只取 NaN 區域
    ut_smooth = ndimage.median_filter(ut, size=3)

    # 建立輸出陣列:保留原始有效值,填充平滑後的 NaN 區域
    uo = ui.copy()
    uo[nan_mask] = ut_smooth[nan_mask]

    return uo


# 額外提供批次處理函數
def interp_vector_field(
    u: np.ndarray,
    v: np.ndarray,
    method: str = 'linear'
) -> Tuple[np.ndarray, np.ndarray]:
    """
    向量場插值 (同時處理 u 和 v 分量)

    參數:
        u, v: 向量場的兩個分量
        method: 'linear', 'spline', 或 'nan'

    優化: 避免重複的方法查找
    """
    interp_func = {
        'linear': interp_linear,
        'spline': interp_spline,
        'nan': interp_nan
    }.get(method, interp_linear)

    return interp_func(u), interp_func(v)
