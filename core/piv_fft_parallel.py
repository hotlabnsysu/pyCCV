"""
piv_fft_parallel.py — piv_fft_multi 的多核心包裝版本。

透過 scipy.fft.set_workers 將底層所有 FFT 運算（fft2 / ifft2）
自動分配到多個 CPU 執行緒，無需改動核心演算法。

核心演算法維持在 piv_fft.py 中，此模組僅作薄層包裝，
消除原有的約 1280 行代碼重複（Phase 5A 重構）。
"""

import numpy as np
import scipy.fft as _sfft

from .piv_fft import piv_fft_multi


def piv_fft_multi_parallel(
    image1: np.ndarray,
    image2: np.ndarray,
    num_workers: int = None,
    **kwargs,
) -> tuple:
    """
    piv_fft_multi 的多核心包裝版本。

    透過 scipy.fft.set_workers 機制，將底層所有 FFT
    運算（fft2 / ifft2）自動分配到多個 CPU 執行緒，無需改動核心演算法。

    Parameters
    ----------
    image1, image2 : np.ndarray
        輸入影像對。
    num_workers : int, optional
        FFT 使用的執行緒數。None / -1 代表使用所有可用核心。
    **kwargs
        其餘參數完整轉發給 piv_fft_multi。

    Returns
    -------
    tuple : (x, y, u, v, type_vector)
    """
    # num_workers=None 或 0 時退回 scipy 預設（等同單執行緒）
    workers = num_workers if (num_workers is not None and num_workers != 0) else 1

    # set_workers 為 context-free 設定，執行完後務必還原
    prev_workers = _sfft.get_workers()
    try:
        _sfft.set_workers(workers)
        return piv_fft_multi(image1, image2, **kwargs)
    finally:
        # 確保即使拋出例外也能還原，避免影響其他呼叫
        _sfft.set_workers(prev_workers)
