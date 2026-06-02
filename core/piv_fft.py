"""
piv_fft.py - FFT 互相關 PIV 分析核心


實作多重解析度（multi-pass）FFT 互相關，支援：
- 多次 pass (1~4 次)
- 子像素定位 (3-pt Gauss / 2D Gauss)
- Window 變形 (linear / spline) - 使用 sub-pixel 插值
- 重複相關增強 (5方向乘積) - DDC (Deformation Correction Correlation)
- 自相關抑制 (Pass 1) 與 峰值搜尋限制 (Multi-pass)
"""

import numpy as np
from concurrent.futures import CancelledError
from scipy import ndimage
from scipy.fft import fft2, ifft2
from scipy.interpolate import RectBivariateSpline
from functools import lru_cache

# 使用 postprocess 模組的函數以避免重複
from .postprocess import piv_lab_post_proc

from config import PERFORMANCE_SETTINGS as _PERF
_FFT_CHUNK_SIZE = _PERF.get("fft_chunk_size", 1024)

# PIV uses single-precision FFTs by default: complex64 transforms are roughly
# 2x faster and halve memory bandwidth. PIV peak detection's noise floor is
# well above float32's precision limit (sub-pixel < 0.01 px is unaffected).
_PIV_FLOAT = np.float32

# Sub-pixel 2D Gauss fitting 常數係數矩陣 (axis0=j, axis1=i)
_COEFF_C10 = np.array([[-1, 0, 1], [-1, 0, 1], [-1, 0, 1]], dtype=_PIV_FLOAT)
_COEFF_C01 = np.array([[-1, -1, -1], [0, 0, 0], [1, 1, 1]], dtype=_PIV_FLOAT)
_COEFF_C11 = np.array([[1, 0, -1], [0, 0, 0], [-1, 0, 1]], dtype=_PIV_FLOAT)
_COEFF_C20 = np.array([[1, -2, 1], [1, -2, 1], [1, -2, 1]], dtype=_PIV_FLOAT)
_COEFF_C02 = np.array([[1, 1, 1], [-2, -2, -2], [1, 1, 1]], dtype=_PIV_FLOAT)


def piv_fft_multi(
    image1: np.ndarray,
    image2: np.ndarray,
    int_area_1: int = 64,
    step: int = 32,
    sub_pix_method: int = 2,
    mask: np.ndarray = None,
    roi: list = None,
    num_passes: int = 3,
    int_area_2: int = 32,
    int_area_3: int = 16,
    int_area_4: int = 16,
    int_area_5: int = 16,
    int_area_6: int = 16,
    window_deform: str = "linear",
    repeat_corr: bool = False,
    disable_autocorr: bool = True,
    do_pad: bool = True,
    cancel_event=None,
) -> tuple:
    """
    多重解析度 FFT 互相關 PIV 分析

    Parameters
    ----------
    image1, image2 : np.ndarray
        輸入影像對 (灰階)
    intArea1 : int
        第一次 pass 的 interrogation window 大小
    step : int
        步進大小 (通常為 intArea1 * overlap)
    subpixMethod : int
        子像素擬合方法 (1=3-pt Gauss, 2=2D Gauss)
    mask : np.ndarray, optional
        遮罩區域
    roi : list, optional
        ROI [x, y, width, height]
    numPasses : int
        pass 次數
    intArea2, intArea3, intArea4, intArea5, intArea6 : int
        後續 pass 的 window 大小
    windowDeform : str
        Window 變形方法 ("linear" / "spline")
    repeatCorr : bool
        是否重複相關 (5方向乘積)
    disableAutocorr : bool
        是否抑制自相關
    doPad : bool
        是否使用 padding 進行線性相關

    Returns
    -------
    x, y : np.ndarray
        網格座標
    u, v : np.ndarray
        速度分量
    typeVector : np.ndarray
        向量類型 (1=正常, 0=遮罩)
    """
    # 處理 ROI
    if roi is not None and len(roi) == 4:
        x_roi, y_roi, width_roi, height_roi = roi
        img_1_roi = image1[y_roi:y_roi + height_roi, x_roi:x_roi + width_roi].astype(_PIV_FLOAT)
        img_2_roi = image2[y_roi:y_roi + height_roi, x_roi:x_roi + width_roi].astype(_PIV_FLOAT)
    else:
        x_roi, y_roi = 0, 0
        img_1_roi = image1.astype(_PIV_FLOAT)
        img_2_roi = image2.astype(_PIV_FLOAT)

    # 保存原始影像供 multi-pass 使用
    gen_img_1_roi = img_1_roi.copy()
    gen_img_2_roi = img_2_roi.copy()

    # 處理 mask
    if mask is not None:
        gen_mask = mask.copy()
    else:
        gen_mask = np.zeros(img_1_roi.shape, dtype=_PIV_FLOAT)

    inter_area = int_area_1
    current_step = step
    if current_step < 1:
        raise ValueError(f"step must be >= 1, got {current_step} (int_area_1={int_area_1})")

    # 計算網格範圍 (
    min_iy = 1 + int(np.ceil(inter_area / 2))
    min_ix = 1 + int(np.ceil(inter_area / 2))
    max_iy = current_step * (img_1_roi.shape[0] // current_step) - (inter_area - 1) + int(np.ceil(inter_area / 2))
    max_ix = current_step * (img_1_roi.shape[1] // current_step) - (inter_area - 1) + int(np.ceil(inter_area / 2))

    num_elements_y = (max_iy - min_iy) // current_step + 1
    num_elements_x = (max_ix - min_ix) // current_step + 1

    if num_elements_y < 1 or num_elements_x < 1:
        raise ValueError(
            f"Interrogation area {inter_area}px exceeds image "
            f"dimensions {img_1_roi.shape} — reduce window size"
        )

    # 置中調整 (
    la_y, la_x = min_iy, min_ix
    lu_y = img_1_roi.shape[0] - max_iy
    lu_x = img_1_roi.shape[1] - max_ix
    shift_4_center_y = max(0, round((lu_y - la_y) / 2))
    shift_4_center_x = max(0, round((lu_x - la_x) / 2))

    min_iy += shift_4_center_y
    min_ix += shift_4_center_x
    max_iy += shift_4_center_y
    max_ix += shift_4_center_x

    # Padding (
    pad_size = int(np.ceil(inter_area / 2))
    pad_value = img_1_roi.min()
    img_1_padded = np.pad(img_1_roi, pad_size, mode='constant', constant_values=pad_value)
    img_2_padded = np.pad(img_2_roi, pad_size, mode='constant', constant_values=pad_value)
    mask_padded = np.pad(gen_mask, pad_size, mode='constant', constant_values=0)

    # 子像素偏移 (
    sub_pix_offset = 1.0 if inter_area % 2 == 0 else 0.5

    # 第一次 pass - 使用向量化處理
    x_table, y_table, u_table, v_table, type_vector = _first_pass(
        img_1_padded, img_2_padded, mask_padded,
        min_ix, min_iy, max_ix, max_iy, current_step,
        inter_area, num_elements_x, num_elements_y,
        pad_size, sub_pix_offset, sub_pix_method,
        do_pad, disable_autocorr, repeat_corr,
        x_roi, y_roi, cancel_event
    )

    # Multi-pass (
    int_areas = [int_area_2, int_area_3, int_area_4, int_area_5, int_area_6]
    for pass_num in range(1, num_passes):
        if pass_num > len(int_areas):
            break

        # 後處理驗證 (
        u_table, v_table = piv_lab_post_proc(u_table, v_table)

        # 填補 NaN (
        u_table = inpaint_nans(u_table, method=4)
        v_table = inpaint_nans(v_table, method=4)

        if np.all(u_table == 0) and np.all(v_table == 0):
            raise ValueError("All vectors invalid after inpainting — skipping pair")

        # 平滑預測器 (
        if pass_num < num_passes - 1:
            # 較強平滑
            u_table = ndimage.gaussian_filter(u_table, sigma=1.5)
            v_table = ndimage.gaussian_filter(v_table, sigma=1.5)
        else:
            # 較弱平滑
            u_table = ndimage.gaussian_filter(u_table, sigma=1.0)
            v_table = ndimage.gaussian_filter(v_table, sigma=1.0)

        # 更新 interrogation area (
        inter_area = int_areas[pass_num - 1]
        current_step = inter_area // 2

        # 重新計算網格 (
        min_iy = 1 + int(np.ceil(inter_area / 2))
        min_ix = 1 + int(np.ceil(inter_area / 2))
        max_iy = current_step * (gen_img_1_roi.shape[0] // current_step) - (inter_area - 1) + int(np.ceil(inter_area / 2))
        max_ix = current_step * (gen_img_1_roi.shape[1] // current_step) - (inter_area - 1) + int(np.ceil(inter_area / 2))

        new_num_elements_y = (max_iy - min_iy) // current_step + 1
        new_num_elements_x = (max_ix - min_ix) // current_step + 1

        # 置中調整
        la_y, la_x = min_iy, min_ix
        lu_y = gen_img_1_roi.shape[0] - max_iy
        lu_x = gen_img_1_roi.shape[1] - max_ix
        shift_4_center_y = max(0, round((lu_y - la_y) / 2))
        shift_4_center_x = max(0, round((lu_x - la_x) / 2))

        min_iy += shift_4_center_y
        min_ix += shift_4_center_x
        max_iy += shift_4_center_y
        max_ix += shift_4_center_x

        # 重新 padding
        pad_size = int(np.ceil(inter_area / 2))
        img_1_padded = np.pad(gen_img_1_roi, pad_size, mode='constant', constant_values=gen_img_1_roi.min())
        img_2_padded = np.pad(gen_img_2_roi, pad_size, mode='constant', constant_values=gen_img_1_roi.min())
        mask_padded = np.pad(gen_mask, pad_size, mode='constant', constant_values=0)

        sub_pix_offset = 1.0 if inter_area % 2 == 0 else 0.5

        # 插值舊向量場到新網格 (
        # : utable=interp2(xtable_old,ytable_old,utable,xtable,ytable,'*spline');
        # 這裡必須使用「座標空間」進行插值，不是索引空間
        
        # 先計算新的座標表 (
        # : xtable = repmat((minix:step:maxix), numelementsy, 1) + interrogationarea/2;
        # : ytable = repmat((miniy:step:maxiy)', 1, numelementsx) + interrogationarea/2;
        new_y_1d = min_iy + np.arange(new_num_elements_y) * current_step + inter_area / 2
        new_x_1d = min_ix + np.arange(new_num_elements_x) * current_step + inter_area / 2
        new_x_table, new_y_table = np.meshgrid(new_x_1d, new_y_1d)
        
        # 舊座標 (x_table, y_table 是上一 pass 的座標)
        old_y_coords = y_table[:, 0]  # 取第一列作為 Y 座標
        old_x_coords = x_table[0, :]  # 取第一行作為 X 座標
        
        # 新座標
        new_y_coords = new_y_table[:, 0]
        new_x_coords = new_x_table[0, :]
        
        # 使用 interp2 等效方法（座標空間插值）(
        # 注意：新座標可能超出舊座標範圍，需要特別處理
        #  的 interp2 對超出範圍的值返回 NaN，然後由 inpaint_nans 填補
        # 這裡使用 zoom 進行網格大小調整更為穩健
        if len(old_y_coords) > 1 and len(old_x_coords) > 1:
            # 使用 scipy.ndimage.zoom 進行調整
            # 這會正確處理邊緣外推問題
            from scipy.ndimage import zoom
            zoom_y = new_num_elements_y / u_table.shape[0]
            zoom_x = new_num_elements_x / u_table.shape[1]

            if zoom_y > 0 and zoom_x > 0:
                order = min(3, u_table.shape[0] - 1, u_table.shape[1] - 1)
                u_table = zoom(u_table, (zoom_y, zoom_x), order=order)
                v_table = zoom(v_table, (zoom_y, zoom_x), order=order)

                target = (new_num_elements_y, new_num_elements_x)
                if u_table.shape != target:
                    u_table = u_table[:target[0], :target[1]]
                    v_table = v_table[:target[0], :target[1]]
                    if u_table.shape[0] < target[0]:
                        u_table = np.pad(u_table, ((0, target[0] - u_table.shape[0]), (0, 0)), mode='edge')
                        v_table = np.pad(v_table, ((0, target[0] - v_table.shape[0]), (0, 0)), mode='edge')
                    if u_table.shape[1] < target[1]:
                        u_table = np.pad(u_table, ((0, 0), (0, target[1] - u_table.shape[1])), mode='edge')
                        v_table = np.pad(v_table, ((0, 0), (0, target[1] - v_table.shape[1])), mode='edge')

        num_elements_y = new_num_elements_y
        num_elements_x = new_num_elements_x

        # ================================================================
        # 影像變形 (
        # ================================================================
        
        # 對 u/v table 做 padarray([1,1], 'replicate') (
        u_table_1 = np.pad(u_table, ((1, 1), (1, 1)), mode='edge')
        v_table_1 = np.pad(v_table, ((1, 1), (1, 1)), mode='edge')
        
        # 建立擴展的座標 xtable_1, ytable_1 (
        #  使用 interp1 線性外推
        x_first = new_x_table[0, :]
        x_idx = np.arange(1, len(x_first) + 1)  # 1-indexed 
        x_idx_extrap = np.arange(0, len(x_first) + 2)  # 0 到 len+1
        x_extrap = np.interp(x_idx_extrap, x_idx, x_first, 
                           left=x_first[0] - (x_first[1] - x_first[0]) if len(x_first) > 1 else x_first[0],
                           right=x_first[-1] + (x_first[-1] - x_first[-2]) if len(x_first) > 1 else x_first[-1])
        x_table_1 = np.tile(x_extrap, (new_num_elements_y + 2, 1))
        
        y_first = new_y_table[:, 0]
        y_idx = np.arange(1, len(y_first) + 1)
        y_idx_extrap = np.arange(0, len(y_first) + 2)
        y_extrap = np.interp(y_idx_extrap, y_idx, y_first,
                           left=y_first[0] - (y_first[1] - y_first[0]) if len(y_first) > 1 else y_first[0],
                           right=y_first[-1] + (y_first[-1] - y_first[-2]) if len(y_first) > 1 else y_first[-1])
        y_table_1 = np.tile(y_extrap.reshape(-1, 1), (1, new_num_elements_x + 2))
        
        # X, Y, U, V 是擴展後的座標和速度場 (
        X = x_table_1
        Y = y_table_1
        U = u_table_1
        V = v_table_1
        
        # 建立 pixel 解析度座標網格 (
        # : X1=X(1,1):1:X(1,end)-1
        # : Y1=(Y(1,1):1:Y(end,1)-1)'
        x1_start = int(X[0, 0])
        x1_end = int(X[0, -1])  # 不包含最後一個
        y1_start = int(Y[0, 0])
        y1_end = int(Y[-1, 0])  # 不包含最後一個
        
        X1 = np.arange(x1_start, x1_end)
        Y1 = np.arange(y1_start, y1_end)
        
        if len(X1) == 0 or len(Y1) == 0:
            img_2_deformed = gen_img_2_roi.copy()
            U1 = np.zeros((1, 1))
            V1 = np.zeros((1, 1))
            xb, yb = 0, 0
        else:
            x1_grid, y1_grid = np.meshgrid(X1, Y1)
            
            # 將 U, V 插值到 pixel 解析度 (
            # : U1 = interp2(X,Y,U,X1,Y1,'*linear');
            try:
                x_vec = X[0, :]
                y_vec = Y[:, 0]
                u_interp_func = RectBivariateSpline(y_vec, x_vec, U, kx=1, ky=1)
                v_interp_func = RectBivariateSpline(y_vec, x_vec, V, kx=1, ky=1)
                U1 = u_interp_func(Y1, X1)
                V1 = v_interp_func(Y1, X1)
            except Exception:
                U1 = np.full_like(x1_grid, np.nanmean(U), dtype=_PIV_FLOAT)
                V1 = np.full_like(x1_grid, np.nanmean(V), dtype=_PIV_FLOAT)
            
            # 影像變形 (
            # : image2_crop_i1 = interp2(1:size(image2_roi,2), (1:size(image2_roi,1))', 
            #                                  double(image2_roi), X1+U1, Y1+V1, imdeform)
            # 注意： 的 image2_roi 是 **padded** 的！（見 L367-369）
            # 座標 X1+U1, Y1+V1 是相對於 padded 影像的 1-indexed 座標
            if window_deform == "spline":
                interp_order = 3
            else:
                interp_order = 1
            
            # 目標座標：X1+U1, Y1+V1，這是 1-indexed  座標
            # 對應 padded 影像的座標系
            target_y = y1_grid + V1
            target_x = x1_grid + U1
            
            # map_coordinates 需要 0-indexed 座標
            # 使用 img_2_padded（padded 影像）進行插值！
            img_2_deformed = ndimage.map_coordinates(
                img_2_padded,
                [target_y - 1, target_x - 1],  # 轉換到 0-indexed
                order=interp_order,
                mode='constant',
                cval=0
            )
            
            # 找到 xb, yb (
            # : xb = find(X1(1,:) == xtable_1(1,1))
            # : yb = find(Y1(:,1) == ytable_1(1,1))
            # X1 是 1D 陣列，X[0,0] 是 xtable_1(1,1)
            xb_matches = np.where(X1 == int(X[0, 0]))[0]
            yb_matches = np.where(Y1 == int(Y[0, 0]))[0]
            xb = int(xb_matches[0]) if len(xb_matches) > 0 else 0
            yb = int(yb_matches[0]) if len(yb_matches) > 0 else 0

        new_u_table, new_v_table, type_vector = _batch_process_pass(
            img_1_padded, img_2_padded, img_2_deformed, gen_img_2_roi, mask_padded,
            min_ix, min_iy, current_step, inter_area, pad_size,
            new_num_elements_x, new_num_elements_y,
            u_table, v_table,  # predictors
            xb, yb,            # offsets from deformation
            x_roi, y_roi,      # absolute ROI offsets
            U1, V1,            # deformation fields (for repeat corr)
            sub_pix_method, sub_pix_offset,
            do_pad, disable_autocorr, repeat_corr,
            pass_num, num_passes, window_deform,
            cancel_event
        )

        x_table = new_x_table
        y_table = new_y_table
        u_table = new_u_table
        v_table = new_v_table

    # 調整座標到原始影像 (
    x_table = x_table - int(np.ceil(inter_area / 2)) + x_roi
    y_table = y_table - int(np.ceil(inter_area / 2)) + y_roi

    return x_table, y_table, u_table, v_table, type_vector


def _first_pass(
    img_1_padded, img_2_padded, mask_padded,
    min_ix, min_iy, max_ix, max_iy, current_step,
    inter_area, num_elements_x, num_elements_y,
    pad_size, sub_pix_offset, sub_pix_method,
    do_pad, disable_autocorr, repeat_corr,
    x_roi, y_roi, cancel_event=None
):
    """第一次 pass 處理 - 向量化版本"""
    # 預計算所有中心座標
    iy_grid, ix_grid = np.meshgrid(np.arange(num_elements_y), np.arange(num_elements_x), indexing='ij')
    centers_y = min_iy + iy_grid * current_step
    centers_x = min_ix + ix_grid * current_step
    
    # 批次 window 擷取
    wins1 = _batch_extract_windows(img_1_padded, centers_y, centers_x, inter_area, pad_size).reshape(-1, inter_area, inter_area)
    wins2 = _batch_extract_windows(img_2_padded, centers_y, centers_x, inter_area, pad_size).reshape(-1, inter_area, inter_area)
    
    # 檢查 mask (批次)
    mask_wins = _batch_extract_windows(mask_padded, centers_y, centers_x, inter_area, pad_size).reshape(-1, inter_area, inter_area)
    # 任何像素 > 0 即視為 masked
    # axis=(1,2) 檢查每個 window
    valid_mask = ~np.any(mask_wins > 0, axis=(1, 2))
    
    # 初始化結果
    u_utils = np.full(num_elements_y * num_elements_x, np.nan)
    v_utils = np.full(num_elements_y * num_elements_x, np.nan)
    type_vec = np.ones(num_elements_y * num_elements_x, dtype=np.int32)
    type_vec[~valid_mask] = 0
    
    # 只對 valid windows 進行 FFT
    num_valid = np.sum(valid_mask)
    if num_valid > 0:
        valid_wins1 = wins1[valid_mask]
        valid_wins2 = wins2[valid_mask]
        
        # 批次 FFT 相關
        corr_stack = _batch_fft_correlate(valid_wins1, valid_wins2, do_pad, inter_area, cancel_event)

        # 後處理：Repeat Correlation & Autocorr (混合模式: 批次轉迴圈以確保數值一致性)
        # 由於 repeat_corr 邏輯複雜且涉及邊界檢查，這裡對 valid index 進行迴圈
        valid_indices = np.where(valid_mask.flatten())[0]
        
        # 準備 Autocorr filter (若需要)
        h_auto = None
        if disable_autocorr:
            h = _gaussian_filter(3, 1.5)
            h = h / h[1, 1]
            h_auto = 1 - h
            
        # Phase 3A: 批次 Repeat Correlation
        if repeat_corr:
            corr_stack = _batch_apply_repeat_corr_first_pass(
                img_1_padded, img_2_padded, min_ix, min_iy,
                current_step, inter_area, valid_indices, num_elements_x,
                pad_size, do_pad, corr_stack
            )

        # Phase 1C: 批次 Autocorr Suppression（c_y/c_x 對所有 window 相同）
        if disable_autocorr and h_auto is not None:
            c_y = inter_area // 2 + int(sub_pix_offset) - 1
            c_x = inter_area // 2 + int(sub_pix_offset) - 1
            if 0 <= c_y - 1 and c_y + 2 <= corr_stack.shape[1] and \
               0 <= c_x - 1 and c_x + 2 <= corr_stack.shape[2]:
                corr_stack[:, c_y - 1:c_y + 2, c_x - 1:c_x + 2] *= h_auto

        # 批次正規化
        c_min = corr_stack.reshape(num_valid, -1).min(axis=1)[:, None, None]
        c_max = corr_stack.reshape(num_valid, -1).max(axis=1)[:, None, None]
        
        # 避免除以零
        diff = c_max - c_min
        mask_norm = diff > 0
        
        # 使用 where 避免全零 window 產生 NaN
        corr_norm = np.zeros_like(corr_stack)
        np.divide((corr_stack - c_min) * 255, diff, out=corr_norm, where=mask_norm)
        
        # 批次峰值搜尋
        peak_y, peak_x = _batch_find_peaks(corr_norm)
        
        # 批次子像素擬合
        # 過濾邊界峰值 (
        # 注意：peak_x/y 是 0-indexed，範圍 0~N-1
        #  條件相當於 0-indexed 的 1 <= p <= N-2 (或者 Python 的 1 < p < N-1 不含邊界)
        # 安全範圍應為 [1, N-2]
        
        is_safe = (peak_x > 1) & (peak_x < inter_area - 1) & \
                  (peak_y > 1) & (peak_y < inter_area - 1)
        
        sub_x = peak_x.astype(_PIV_FLOAT)
        sub_y = peak_y.astype(_PIV_FLOAT)
        
        # 對安全點做子像素計算
        if np.any(is_safe):
            safe_corr = corr_norm[is_safe]
            safe_px = peak_x[is_safe]
            safe_py = peak_y[is_safe]
            
            if sub_pix_method == 1:
                dx, dy = _batch_subpix_gauss(safe_corr, safe_px, safe_py)
            else:
                dx, dy = _batch_subpix_2d_gauss(safe_corr, safe_px, safe_py)
            
            sub_x[is_safe] = dx
            sub_y[is_safe] = dy
            
        # 填值回結果陣列 (僅對 safe 且 valid 的點填入位移，否則 NaN)
        # 位移計算: sub_pos + 1 - center
        # center = inter_area / 2 + sub_pix_offset
        
        res_u = np.full(num_valid, np.nan)
        res_v = np.full(num_valid, np.nan)
        
        # 只有在 is_safe 為 True 的地方才有有效位移
        # 不安全點保持 NaN (
        
        offset = inter_area / 2 + sub_pix_offset
        # Python sub_x + 1 對應用於  1-indexed 公式
        
        res_u[is_safe] = sub_x[is_safe] + 1 - offset
        res_v[is_safe] = sub_y[is_safe] + 1 - offset
        
        u_utils[valid_mask.flatten()] = res_u
        v_utils[valid_mask.flatten()] = res_v

    # 座標計算
    x_table = centers_x + inter_area // 2
    y_table = centers_y + inter_area // 2
    
    return x_table, y_table, u_utils.reshape(num_elements_y, num_elements_x), v_utils.reshape(num_elements_y, num_elements_x), type_vec.reshape(num_elements_y, num_elements_x)


def _batch_process_pass(
    img_1_padded, img_2_padded, img_2_deformed, gen_img_2_roi, mask_padded,
    min_ix, min_iy, current_step, inter_area, pad_size,
    num_elements_x, num_elements_y,
    u_table_pred, v_table_pred,
    xb, yb, x_roi, y_roi, U1, V1,
    sub_pix_method, sub_pix_offset,
    do_pad, disable_autocorr, repeat_corr,
    pass_num, num_passes, window_deform,
    cancel_event=None
):
    """Multi-pass 核心處理 - 向量化版本"""
    # 網格座標
    iy_grid, ix_grid = np.meshgrid(np.arange(num_elements_y), np.arange(num_elements_x), indexing='ij')
    
    # 預測值 (Fallback用)
    # 對應原版 /Python 邏輯: if iy < u_table.shape[0] and ix < u_table.shape[1]: pred = u_table[iy, ix]; else: pred = 0
    pred_u_flat = np.zeros(num_elements_x * num_elements_y)
    pred_v_flat = np.zeros(num_elements_x * num_elements_y)
    
    # 建立索引遮罩：哪些位置在舊網格範圍內
    in_bounds_y = iy_grid < u_table_pred.shape[0]
    in_bounds_x = ix_grid < u_table_pred.shape[1]
    in_bounds = in_bounds_y & in_bounds_x
    
    # 對在界內的點，直接索引
    if np.any(in_bounds):
        valid_iy = iy_grid[in_bounds]
        valid_ix = ix_grid[in_bounds]
        pred_u_flat[in_bounds.flatten()] = u_table_pred[valid_iy, valid_ix]
        pred_v_flat[in_bounds.flatten()] = v_table_pred[valid_iy, valid_ix]
    
    # 超界的點已經在初始化時設為 0（與原版一致）

    # Image 1 Windows extraction
    # centers
    centers_y = min_iy + iy_grid * current_step
    centers_x = min_ix + ix_grid * current_step
    
    wins1 = _batch_extract_windows(img_1_padded, centers_y, centers_x, inter_area, pad_size).reshape(-1, inter_area, inter_area)
    
    # Mask checking
    mask_wins = _batch_extract_windows(mask_padded, centers_y, centers_x, inter_area, pad_size).reshape(-1, inter_area, inter_area)
    masked_flags = np.any(mask_wins > 0, axis=(1, 2))
    
    # Image 2 Deformed Windows extraction
    # 計算 deformed 座標
    # deform_y1 = yb + current_step * iy  ( L432 邏輯)
    deform_y1s = (yb + current_step * iy_grid).astype(int)
    deform_x1s = (xb + current_step * ix_grid).astype(int)
    
    # 提取 deformed windows
    # 這裡無法簡單使用 _batch_extract_windows 因為不是從 padded 規則取，而是直接從 deformed_img 取
    # 且邊界檢查邏輯獨特
    
    # 建立一個 valid map，包含 mask 檢查和邊界檢查
    valid_flags = ~masked_flags
    
    # 邊界檢查 Image 2
    H2, W2 = img_2_deformed.shape
    valid_flags &= (deform_y1s.flatten() >= 0)
    valid_flags &= (deform_x1s.flatten() >= 0)
    valid_flags &= (deform_y1s.flatten() + inter_area <= H2)
    valid_flags &= (deform_x1s.flatten() + inter_area <= W2)
    
    # 初始化結果
    res_u = pred_u_flat.copy()  # 預設為預測值
    res_v = pred_v_flat.copy()
    type_vec = np.ones_like(valid_flags, dtype=np.int32) 
    
    # 更新 Masked 區域
    type_vec[masked_flags] = 0
    res_u[masked_flags] = np.nan
    res_v[masked_flags] = np.nan
    
    # 僅處理 Valid
    num_valid = np.sum(valid_flags)
    
    if num_valid > 0:
        valid_idx = np.where(valid_flags)[0]
        
        v_wins1 = wins1[valid_flags]
        
        # 批次提取 Image 2 Windows
        # 使用 Advanced Indexing
        # 需構建索引 grid
        # 每個 window: [y1:y1+H, x1:x1+W]
        # 構建 base grid (0..H-1, 0..W-1)
        base_y, base_x = np.meshgrid(np.arange(inter_area), np.arange(inter_area), indexing='ij')
        
        # 擴展到 N 個 window: N, H, W
        v_y1s = deform_y1s.flatten()[valid_flags]
        v_x1s = deform_x1s.flatten()[valid_flags]
        
        # Phase 1A: 向量化 fancy indexing 替代 Python loop
        Y_indices = v_y1s[:, None, None] + base_y[None, :, :]
        X_indices = v_x1s[:, None, None] + base_x[None, :, :]
        v_wins2 = img_2_deformed[Y_indices, X_indices]
        
        # 批次 FFT
        is_last_pass = (pass_num == num_passes - 1)
        corr_stack = _batch_fft_correlate(v_wins1, v_wins2, (do_pad and is_last_pass), inter_area, cancel_event)
        
        # 後處理 (Repeat Corr & Peak Limiter)
        # 準備 Peak Limiter Mask
        search_mask = None
        if disable_autocorr:
            h = _disk_filter(4) # Peak search radius 4
            h = h / np.max(h)
            
            # 構建基礎 mask
            base_mask = np.zeros((inter_area, inter_area))
            c_y = inter_area // 2 + int(sub_pix_offset) - 1
            c_x = inter_area // 2 + int(sub_pix_offset) - 1
            
            h_y, h_x = h.shape
            y1m = c_y - h_y // 2
            y2m = y1m + h_y
            x1m = c_x - h_x // 2
            x2m = x1m + h_x
            
            # Clipping logic
            dy1, dy2, dx1, dx2 = 0, h_y, 0, h_x
            if y1m < 0: dy1, y1m = -y1m, 0
            if y2m > inter_area: dy2, y2m = h_y - (y2m - inter_area), inter_area
            if x1m < 0: dx1, x1m = -x1m, 0
            if x2m > inter_area: dx2, x2m = h_x - (x2m - inter_area), inter_area
            
            if dy2 > dy1 and dx2 > dx1:
                base_mask[y1m:y2m, x1m:x2m] = h[dy1:dy2, dx1:dx2]
                search_mask = base_mask
        
        # Phase 3A: 批次 Repeat Correlation
        if repeat_corr and is_last_pass:
            valid_centers_y = centers_y.flatten()[valid_idx]
            valid_centers_x = centers_x.flatten()[valid_idx]
            corr_stack = _batch_apply_repeat_corr(
                img_1_padded, img_2_deformed,
                valid_centers_x, valid_centers_y, inter_area, pad_size,
                xb, yb, current_step,
                do_pad, corr_stack
            )

        # Peak Limiter（search_mask 對所有 window 相同，廣播即可）
        if disable_autocorr and search_mask is not None:
            corr_stack *= search_mask
        
        # 正規化
        c_min = corr_stack.reshape(num_valid, -1).min(axis=1)[:, None, None]
        c_max = corr_stack.reshape(num_valid, -1).max(axis=1)[:, None, None]
        diff = c_max - c_min
        mask_norm = diff > 0
        
        corr_norm = np.zeros_like(corr_stack)
        np.divide((corr_stack - c_min) * 255, diff, out=corr_norm, where=mask_norm)
        
        # 尋找峰值
        peak_y, peak_x = _batch_find_peaks(corr_norm)
        
        # 安全範圍 check (match original: 1 < peak < N-1)
        is_safe = (peak_x > 1) & (peak_x < inter_area - 1) & \
                  (peak_y > 1) & (peak_y < inter_area - 1)
        
        # 子像素
        delta_u = np.zeros(num_valid)
        delta_v = np.zeros(num_valid)
        
        if np.any(is_safe):
            safe_corr = corr_norm[is_safe]
            safe_px = peak_x[is_safe]
            safe_py = peak_y[is_safe]
            
            if sub_pix_method == 1:
                dx, dy = _batch_subpix_gauss(safe_corr, safe_px, safe_py)
            else:
                dx, dy = _batch_subpix_2d_gauss(safe_corr, safe_px, safe_py)
            
            # 位移量計算
            offset = inter_area / 2 + sub_pix_offset
            delta_u[is_safe] = dx + 1 - offset
            delta_v[is_safe] = dy + 1 - offset
            
        # 更新結果 = 預測 + delta
        # 對於不安全的點，delta=0，即保留預測值 (
        # : if peak not near border, u = u_pred + delta; else u = u_pred
        
        res_u[valid_idx] += delta_u
        res_v[valid_idx] += delta_v
        
    return res_u.reshape(num_elements_y, num_elements_x), res_v.reshape(num_elements_y, num_elements_x), type_vec.reshape(num_elements_y, num_elements_x)


# ==============================================================================
# 批次處理輔助函數 (Batch Helper Functions)
# ==============================================================================

def _batch_extract_windows(padded_img, centers_y, centers_x, win_size, pad_size):
    """
    從 padded 影像中批次提取 windows
    回傳形狀: (N_total, win_size, win_size)
    """
    # 計算左上角座標
    y1s = (centers_y - win_size // 2 + pad_size - 1).astype(int).flatten()
    x1s = (centers_x - win_size // 2 + pad_size - 1).astype(int).flatten()
    
    # 邊界檢查
    max_h, max_w = padded_img.shape
    num_wins = len(y1s)
    
    windows = np.zeros((num_wins, win_size, win_size), dtype=padded_img.dtype)
    
    # 檢查是否所有 index 都在範圍內
    valid = (y1s >= 0) & (y1s + win_size <= max_h) & (x1s >= 0) & (x1s + win_size <= max_w)
    
    # 僅提取有效的 (Vectorized Extraction)
    if np.any(valid):
        valid_indices = np.where(valid)[0]
        
        # 使用 Fancy Indexing + Broadcasting 替代 Python Loop
        # 1. 取得有效 window 的左上角座標
        vy = y1s[valid_indices]
        vx = x1s[valid_indices]
        
        # 2. 建立 window 內的相對位移索引 (0..win_size-1)
        row_offsets = np.arange(win_size)
        col_offsets = np.arange(win_size)
        
        # 3. 利用廣播建立完整的索引矩陣
        # vy[:, None, None]: (N, 1, 1) - 每個 window 的基底 y
        # row_offsets[None, :, None]: (1, win, 1) - window 內的 row 偏移
        # Y_idx: (N, win, 1) -> broadcasting result
        Y_idx = vy[:, None, None] + row_offsets[None, :, None]
        
        # vx[:, None, None]: (N, 1, 1) - 每個 window 的基底 x
        # col_offsets[None, None, :]: (1, 1, win) - window 內的 col 偏移
        # X_idx: (N, 1, win) -> broadcasting result
        X_idx = vx[:, None, None] + col_offsets[None, None, :]
        
        # 4. 一次性提取所有像素
        # (N, win, 1) 與 (N, 1, win) 廣播成 (N, win, win) 進行索引
        windows[valid_indices] = padded_img[Y_idx, X_idx]
            
    return windows

def _batch_fft_correlate(wins1, wins2, do_pad, inter_area, cancel_event=None):
    """
    批次 FFT 互相關
    wins: (N, H, W)
    """
    N, H, W = wins1.shape

    # 預先配置輸出陣列
    corr_out = np.empty((N, inter_area, inter_area), dtype=_PIV_FLOAT)

    # 預分配 padding 緩衝區（避免每個 chunk 重新 malloc）
    if do_pad:
        pad_h = 2 * inter_area - 1
        buf_size = min(N, _FFT_CHUNK_SIZE)
        pw1 = np.zeros((buf_size, pad_h, pad_h), dtype=_PIV_FLOAT)
        pw2 = np.zeros((buf_size, pad_h, pad_h), dtype=_PIV_FLOAT)
        crop = inter_area // 2 - 1

    # 分塊處理：每次最多 _FFT_CHUNK_SIZE 個 window
    for start_idx in range(0, N, _FFT_CHUNK_SIZE):
        if cancel_event is not None and cancel_event.is_set():
            raise CancelledError("Analysis cancelled by user")

        end_idx = min(start_idx + _FFT_CHUNK_SIZE, N)
        n_chunk = end_idx - start_idx
        c_w1 = wins1[start_idx:end_idx]
        c_w2 = wins2[start_idx:end_idx]

        # 減均值
        c_w1 = c_w1 - np.mean(c_w1, axis=(1, 2), keepdims=True)
        c_w2 = c_w2 - np.mean(c_w2, axis=(1, 2), keepdims=True)

        if do_pad:
            pw1[:n_chunk] = 0
            pw2[:n_chunk] = 0
            pw1[:n_chunk, :inter_area, :inter_area] = c_w1
            pw2[:n_chunk, :inter_area, :inter_area] = c_w2

            f1 = fft2(pw1[:n_chunk], axes=(-2, -1))
            f2 = fft2(pw2[:n_chunk], axes=(-2, -1))

            c = np.real(ifft2(np.conj(f1) * f2, axes=(-2, -1)))
            c = _batch_fft_shift(c)

            corr_out[start_idx:end_idx] = c[:, crop:crop+inter_area, crop:crop+inter_area]

        else:
            f1 = fft2(c_w1, axes=(-2, -1))
            f2 = fft2(c_w2, axes=(-2, -1))
            c = np.real(ifft2(np.conj(f1) * f2, axes=(-2, -1)))
            corr_out[start_idx:end_idx] = _batch_fft_shift(c)

    return corr_out

def _batch_fft_shift(arr):
    """批次 fftshift (對最後兩維)"""
    return np.fft.fftshift(arr, axes=(-2, -1))

def _batch_find_peaks(corr_stack):
    """
    批次尋找峰值
    corr_stack: (N, H, W)
    Returns: (peak_y, peak_x) shape (N,)
    """
    N, H, W = corr_stack.shape
    # Flatten last two dims
    flat_corr = corr_stack.reshape(N, -1)
    peak_indices = np.argmax(flat_corr, axis=1)
    # Unravel
    peak_y, peak_x = np.unravel_index(peak_indices, (H, W))
    return peak_y, peak_x

def _batch_subpix_gauss(corr_stack, peak_x, peak_y):
    """
    批次 3-pt Gaussian
    """
    N = len(peak_x)
    eps = 1e-10
    
    # Advanced indexing to gather neighbors
    # corr_stack shape (N, H, W)
    # indices: (arange(N), y, x)
    idx = np.arange(N)
    
    c = corr_stack
    
    # Val at peak
    f0 = np.log(c[idx, peak_y, peak_x] + eps)
    
    # Y neighbors
    f1y = np.log(c[idx, peak_y-1, peak_x] + eps)
    f2y = np.log(c[idx, peak_y+1, peak_x] + eps)
    denom_y = 2 * f1y - 4 * f0 + 2 * f2y
    
    dy = np.zeros(N)
    mask_y = np.abs(denom_y) > eps
    dy[mask_y] = (f1y[mask_y] - f2y[mask_y]) / denom_y[mask_y]
    sub_y = peak_y + dy
    
    # X neighbors
    f1x = np.log(c[idx, peak_y, peak_x-1] + eps)
    f2x = np.log(c[idx, peak_y, peak_x+1] + eps)
    denom_x = 2 * f1x - 4 * f0 + 2 * f2x
    
    dx = np.zeros(N)
    mask_x = np.abs(denom_x) > eps
    dx[mask_x] = (f1x[mask_x] - f2x[mask_x]) / denom_x[mask_x]
    sub_x = peak_x + dx
    
    return sub_x, sub_y

def _batch_subpix_2d_gauss(corr_stack, peak_x, peak_y):
    """
    批次 2D Gaussian
    """
    N = len(peak_x)
    eps = 1e-10
    idx = np.arange(N)
    
    # 提取 3x3 區域
    # shape (N, 3, 3)
    # y range: peak_y - 1 .. peak_y + 1 (size 3)
    # x range: peak_x - 1 .. peak_x + 1
    
    # 構造 index
    # [i, j] in {-1, 0, 1}
    # c_val[k, i+1, j+1] = log(corr[k, py+j, px+i])
    # 注意迴圈順序: code uses j for y, i for x
    
    # Phase 1B: 向量化 3×3 鄰域提取，替代巢狀 Python loop
    # dy_offsets (j) = axis0, dx_offsets (i) = axis1
    dy_offsets = np.array([-1, 0, 1])
    dx_offsets = np.array([-1, 0, 1])
    # vals shape: (N, 3, 3)
    vals = np.log(corr_stack[
        idx[:, None, None],
        peak_y[:, None, None] + dy_offsets[None, :, None],
        peak_x[:, None, None] + dx_offsets[None, None, :]
    ] + eps)
    c10 = (vals * _COEFF_C10).sum(axis=(1, 2)) / 6
    c01 = (vals * _COEFF_C01).sum(axis=(1, 2)) / 6
    c11 = (vals * _COEFF_C11).sum(axis=(1, 2)) / 4
    c20 = (vals * _COEFF_C20).sum(axis=(1, 2)) / 6
    c02 = (vals * _COEFF_C02).sum(axis=(1, 2)) / 6
    
    denom = 4 * c20 * c02 - c11**2
    
    mask = np.abs(denom) > eps
    
    delta_x = np.zeros(N)
    delta_y = np.zeros(N)
    
    delta_x[mask] = (c11[mask] * c01[mask] - 2 * c10[mask] * c02[mask]) / denom[mask]
    delta_y[mask] = (c11[mask] * c10[mask] - 2 * c01[mask] * c20[mask]) / denom[mask]
    
    return peak_x + delta_x, peak_y + delta_y




def _fft_shift_both(arr: np.ndarray) -> np.ndarray:
    """
    
    先對 axis 0 做 shift，再對 axis 1 做 shift
    """
    return np.fft.fftshift(arr, axes=(0, 1))


@lru_cache(maxsize=16)
def _gaussian_filter(size: int, sigma: float) -> np.ndarray:
    """產生 Gaussian 核心（帶快取）"""
    x = np.arange(size) - size // 2
    y = np.arange(size) - size // 2
    xx, yy = np.meshgrid(x, y)
    kernel = np.exp(-(xx**2 + yy**2) / (2 * sigma**2))
    return kernel


@lru_cache(maxsize=8)
def _disk_filter(radius: int) -> np.ndarray:
    """
    產生 Disk (圓形) 濾波器，模擬  fspecial('disk')
     的 fspecial('disk', r) 產生的矩陣大小為 2*r+1
    """
    size = 2 * radius + 1
    x = np.arange(size) - radius
    y = np.arange(size) - radius
    xx, yy = np.meshgrid(x, y)
    dist = np.sqrt(xx**2 + yy**2)
    
    #  的 disk filter 行為：
    # 像素權重取決於其與中心的距離。如果在圓內則有值。
    # 簡單模擬：中心 radius 內的像素設為 1，邊緣可能有 anti-aliasing (這裡簡化處理)
    k = np.zeros((size, size))
    k[dist <= radius] = 1.0
    
    # 簡單的高斯平滑讓邊緣不那麼銳利 (可選)
    return k


def _batch_apply_repeat_corr_first_pass(
    img_1_padded, img_2_padded, min_ix, min_iy,
    step, inter_area, valid_indices, num_elements_x,
    pad_size, do_pad, corr_stack
):
    """
    Phase 3A: 批次版 repeat_corr（第一 pass）

    將 4 個方向的 shift windows 批次 FFT，取代逐 window 逐方向的個別 FFT 呼叫。
    數值結果與 _apply_repeat_corr_first_pass 完全等效（atol < 1e-10）。

    Parameters
    ----------
    valid_indices   : 1D int array — _first_pass 中的 valid_indices
    corr_stack      : (N_valid, inter_area, inter_area) — in-place 乘積累積
    """
    ms = round(step / 4)
    shifts = [(ms, -ms), (ms, ms), (-ms, -ms), (-ms, ms)]
    H, W = img_1_padded.shape
    row_off = np.arange(inter_area)
    col_off = np.arange(inter_area)

    center_ys = min_iy + (valid_indices // num_elements_x) * step
    center_xs = min_ix + (valid_indices % num_elements_x) * step

    for dy, dx in shifts:
        y1s = center_ys + dy - inter_area // 2 + pad_size
        x1s = center_xs + dx - inter_area // 2 + pad_size
        valid = (y1s >= 0) & (x1s >= 0) & \
                (y1s + inter_area <= H) & (x1s + inter_area <= W)
        if not np.any(valid):
            continue

        vi = np.where(valid)[0]
        nv = len(vi)

        # 向量化提取 windows
        vy1 = y1s[vi]
        vx1 = x1s[vi]
        Y_idx = vy1[:, None, None] + row_off[None, :, None]
        X_idx = vx1[:, None, None] + col_off[None, None, :]
        wins1 = img_1_padded[Y_idx, X_idx].astype(_PIV_FLOAT, copy=False)
        wins2 = img_2_padded[Y_idx, X_idx].astype(_PIV_FLOAT, copy=False)

        if do_pad:
            # 減均值（與原始函數一致）
            wins1 = wins1 - np.mean(wins1, axis=(1, 2), keepdims=True)
            wins2 = wins2 - np.mean(wins2, axis=(1, 2), keepdims=True)
            pad_h = 2 * inter_area - 1
            pw1 = np.zeros((nv, pad_h, pad_h), dtype=_PIV_FLOAT)
            pw2 = np.zeros((nv, pad_h, pad_h), dtype=_PIV_FLOAT)
            pw1[:, :inter_area, :inter_area] = wins1
            pw2[:, :inter_area, :inter_area] = wins2
            f1 = fft2(pw1, axes=(-2, -1))
            f2 = fft2(pw2, axes=(-2, -1))
            c = np.real(ifft2(np.conj(f1) * f2, axes=(-2, -1)))
            c = _batch_fft_shift(c)
            crop = inter_area // 2 - 1
            corr_shifts = c[:, crop:crop + inter_area, crop:crop + inter_area]
        else:
            # 不減均值（與原始函數 else 分支一致）
            f1 = fft2(wins1, axes=(-2, -1))
            f2 = fft2(wins2, axes=(-2, -1))
            c = np.real(ifft2(np.conj(f1) * f2, axes=(-2, -1)))
            corr_shifts = _batch_fft_shift(c)

        corr_stack[vi] *= corr_shifts

    return corr_stack


def _batch_apply_repeat_corr(
    img_1_padded, img_2_deformed,
    center_xs, center_ys, inter_area, pad_size,
    deform_min_x, deform_min_y, step,
    do_pad, corr_stack
):
    """
    Phase 3A: 批次版 repeat_corr（multi-pass）

    數值結果與 _apply_repeat_corr 完全等效（atol < 1e-10）。

    Parameters
    ----------
    center_xs, center_ys : 1D int arrays — valid windows 的中心座標
    corr_stack           : (N_valid, inter_area, inter_area) — in-place 乘積累積
    """
    ms = round(step / 4)
    shifts = [(ms, -ms), (ms, ms), (-ms, -ms), (-ms, ms)]
    H1, W1 = img_1_padded.shape
    Hd, Wd = img_2_deformed.shape
    row_off = np.arange(inter_area)
    col_off = np.arange(inter_area)

    for dy, dx in shifts:
        y1s  = center_ys + dy - inter_area // 2 + pad_size
        x1s  = center_xs + dx - inter_area // 2 + pad_size
        dy1s = (center_ys + dy - inter_area // 2 - deform_min_y).astype(int)
        dx1s = (center_xs + dx - inter_area // 2 - deform_min_x).astype(int)

        valid = (
            (y1s  >= 0) & (x1s  >= 0) &
            (y1s  + inter_area <= H1) & (x1s  + inter_area <= W1) &
            (dy1s >= 0) & (dx1s >= 0) &
            (dy1s + inter_area <= Hd) & (dx1s + inter_area <= Wd)
        )
        if not np.any(valid):
            continue

        vi  = np.where(valid)[0]
        nv  = len(vi)

        # 從 img_1_padded 提取
        vy1 = y1s[vi].astype(int)
        vx1 = x1s[vi].astype(int)
        Y_idx  = vy1[:, None, None] + row_off[None, :, None]
        X_idx  = vx1[:, None, None] + col_off[None, None, :]
        wins1  = img_1_padded[Y_idx, X_idx].astype(_PIV_FLOAT, copy=False)

        # 從 img_2_deformed 提取
        vdy1   = dy1s[vi]
        vdx1   = dx1s[vi]
        DY_idx = vdy1[:, None, None] + row_off[None, :, None]
        DX_idx = vdx1[:, None, None] + col_off[None, None, :]
        wins2  = img_2_deformed[DY_idx, DX_idx].astype(_PIV_FLOAT, copy=False)

        if do_pad:
            wins1 = wins1 - np.mean(wins1, axis=(1, 2), keepdims=True)
            wins2 = wins2 - np.mean(wins2, axis=(1, 2), keepdims=True)
            pad_h = 2 * inter_area - 1
            pw1 = np.zeros((nv, pad_h, pad_h), dtype=_PIV_FLOAT)
            pw2 = np.zeros((nv, pad_h, pad_h), dtype=_PIV_FLOAT)
            pw1[:, :inter_area, :inter_area] = wins1
            pw2[:, :inter_area, :inter_area] = wins2
            f1 = fft2(pw1, axes=(-2, -1))
            f2 = fft2(pw2, axes=(-2, -1))
            c = np.real(ifft2(np.conj(f1) * f2, axes=(-2, -1)))
            c = _batch_fft_shift(c)
            crop = inter_area // 2 - 1
            corr_shifts = c[:, crop:crop + inter_area, crop:crop + inter_area]
        else:
            # 減均值（與原始函數 else 分支一致）
            wins1 -= np.mean(wins1, axis=(1, 2), keepdims=True)
            wins2 -= np.mean(wins2, axis=(1, 2), keepdims=True)
            f1 = fft2(wins1, axes=(-2, -1))
            f2 = fft2(wins2, axes=(-2, -1))
            c = np.real(ifft2(np.conj(f1) * f2, axes=(-2, -1)))
            corr_shifts = _batch_fft_shift(c)

        corr_stack[vi] *= corr_shifts

    return corr_stack


def inpaint_nans(data: np.ndarray, method: int = 4) -> np.ndarray:
    """
    NaN 填補


    Parameters
    ----------
    data : np.ndarray
        含有 NaN 的 2D 陣列
    method : int
        填補方法 (0-5)，預設 4 (Laplacian diffusion fast path / lsqr fallback)

    Returns
    -------
    result : np.ndarray
        填補後的陣列
    """
    n, m = data.shape
    A = data.flatten()
    nm = n * m

    nan_mask = np.isnan(A)
    nan_list = np.where(nan_mask)[0]
    known_list = np.where(~nan_mask)[0]

    nan_count = len(nan_list)
    if nan_count == 0:
        return data.copy()

    if len(known_list) == 0:
        import logging
        logging.getLogger("pyCCV").warning(
            "inpaint_nans: 所有資料均為 NaN (shape=%s)，回傳零矩陣", data.shape)
        return np.zeros_like(data)

    # 轉換為 (row, col) 形式
    nan_rows = nan_list // m
    nan_cols = nan_list % m

    result = A.copy()

    if method == 4:
        nan_ratio = nan_count / nm

        if nan_ratio > 0.30:
            # --- High NaN density: sparse lsqr fallback ---
            # Note: this branch writes into `result` (flat copy of A) and
            # falls through to `return result.reshape(n, m)` at end of function.
            # Spring metaphor: 每個 NaN 點與其水平/垂直鄰居有彈簧連接
            hv_list = [(-1, 0), (1, 0), (0, -1), (0, 1)]
            springs = []

            for i in range(nan_count):
                idx = nan_list[i]
                row = nan_rows[i]
                col = nan_cols[i]

                for dr, dc in hv_list:
                    new_row = row + dr
                    new_col = col + dc
                    if 0 <= new_row < n and 0 <= new_col < m:
                        neighbor_idx = new_row * m + new_col
                        springs.append((idx, neighbor_idx))

            if len(springs) == 0:
                # 沒有彈簧連接，用鄰域均值
                for i in range(nan_count):
                    idx = nan_list[i]
                    row = nan_rows[i]
                    col = nan_cols[i]
                    neighbors = []
                    for dr, dc in hv_list:
                        new_row = row + dr
                        new_col = col + dc
                        if 0 <= new_row < n and 0 <= new_col < m:
                            neighbor_idx = new_row * m + new_col
                            if not np.isnan(A[neighbor_idx]):
                                neighbors.append(A[neighbor_idx])
                    if neighbors:
                        result[idx] = np.mean(neighbors)
                    else:
                        result[idx] = np.nanmean(A)
            else:
                # 建立稀疏矩陣 (COO format — faster than LIL for batch construction)
                num_springs = len(springs)
                springs_arr = np.array(springs, dtype=np.int32)  # shape (num_springs, 2)

                rows = np.tile(np.arange(num_springs, dtype=np.int32), 2)
                cols = np.concatenate([springs_arr[:, 0], springs_arr[:, 1]])
                vals = np.concatenate([np.ones(num_springs), -np.ones(num_springs)])

                from scipy.sparse import coo_matrix
                spring_mat = coo_matrix((vals, (rows, cols)), shape=(num_springs, nm)).tocsr()

                # 分離已知和未知
                # 系統方程: L * x = 0 (spring equilibrium)
                # L_unknown * x_unknown + L_known * x_known = 0
                # L_unknown * x_unknown = - L_known * x_known

                mat_known = spring_mat[:, known_list]
                mat_unknown = spring_mat[:, nan_list]

                rhs = -mat_known @ A[known_list]

                # 使用稀疏求解器 (lsqr for least squares on sparse matrix)
                from scipy.sparse.linalg import lsqr

                try:
                    # lsqr 返回 (x, istop, itn, r1norm, r2norm, anorm, acond, arnorm, xnorm, var)
                    solution = lsqr(mat_unknown, rhs)[0]
                    result[nan_list] = solution
                except Exception:
                    # Fallback: 用鄰域均值
                    for i in range(nan_count):
                        idx = nan_list[i]
                        row = nan_rows[i]
                        col = nan_cols[i]
                        neighbors = []
                        for dr, dc in hv_list:
                            new_row = row + dr
                            new_col = col + dc
                            if 0 <= new_row < n and 0 <= new_col < m:
                                neighbor_idx = new_row * m + new_col
                                if not np.isnan(A[neighbor_idx]):
                                    neighbors.append(A[neighbor_idx])
                        if neighbors:
                            result[idx] = np.mean(neighbors)
                        else:
                            result[idx] = np.nanmean(A)

        else:
            # --- Fast path: iterative Laplacian diffusion ---
            # 4-connected kernel: propagates values from known neighbours into NaN cells
            kernel = np.array([[0, 1, 0], [1, 0, 1], [0, 1, 0]], dtype=np.float64)
            diff_result = data.copy()
            # Enough iterations to propagate across the longest diagonal
            max_iter = min(500, 10 * (n + m))

            for _ in range(max_iter):
                nan_pos = np.isnan(diff_result)
                if not np.any(nan_pos):
                    break
                numerator = ndimage.convolve(
                    np.nan_to_num(diff_result, nan=0.0), kernel, mode='reflect'
                )
                denom = ndimage.convolve(
                    (~nan_pos).astype(np.float64), kernel, mode='reflect'
                )
                new_vals = numerator / np.where(denom > 0, denom, 1.0)
                # Only fill cells that have at least one known neighbour; cells
                # entirely surrounded by NaN stay NaN and receive values once
                # the boundary propagates inward in later iterations.
                fillable = nan_pos & (denom > 0)
                diff_result[fillable] = new_vals[fillable]

            # Fill any remaining isolated NaNs (entire neighbourhood was NaN)
            if np.any(np.isnan(diff_result)):
                diff_result[np.isnan(diff_result)] = np.nanmean(data)

            return diff_result.reshape(n, m)

    elif method == 0 or method == 1:
        # del^2 方法 (簡化版)
        from scipy.ndimage import generic_filter

        def nan_mean(values):
            valid = values[~np.isnan(values)]
            return np.mean(valid) if len(valid) > 0 else np.nan

        temp = data.copy()
        for _ in range(10):  # 迭代多次
            filled = generic_filter(temp, nan_mean, size=3, mode='reflect')
            temp[np.isnan(temp)] = filled[np.isnan(temp)]
            if not np.any(np.isnan(temp)):
                break

        if np.any(np.isnan(temp)):
            temp[np.isnan(temp)] = np.nanmean(data)

        return temp

    else:
        # 其他方法：使用簡單的鄰域平均
        from scipy.ndimage import generic_filter

        def nan_mean(values):
            valid = values[~np.isnan(values)]
            return np.mean(valid) if len(valid) > 0 else np.nan

        filled = generic_filter(data, nan_mean, size=3, mode='reflect')
        result = data.copy().flatten()
        result[nan_list] = filled.flatten()[nan_list]

        if np.any(np.isnan(result)):
            result[np.isnan(result)] = np.nanmean(data)

    return result.reshape(n, m)
