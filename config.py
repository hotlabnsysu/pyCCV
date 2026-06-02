"""
pyCCV MAIN 預設參數配置
對應 MATLAB MPIVlab 1.14 的 a0, a1, a3 結構
"""

# ========== UI 字型設定 ==========
UI_FONT_FAMILY = "Microsoft JhengHei UI"
UI_FONT_SIZE_BASE = 13

# ========== 基本設定 (對應 a0) ==========
BASIC_SETTINGS = {
    # 目錄設定
    "input_dir": "",             # 輸入目錄
    "output_dir": "",            # 輸出目錄
    
    # 自定義選取功能
    "custom_select_enabled": False,   # 啟用自定義選取
    "custom_selected_images": [],     # 已選取的影像檔案路徑清單

    # 輸出選項
    "export_smooth": False,      # 輸出平滑+插值+過濾結果
    "export_interp": False,      # 輸出插值+過濾結果
    "export_filt": False,        # 輸出過濾結果
    "export_raw": False,         # 輸出原始結果
    
    # 繪圖選項
    "plot_now": 3,               # 0=不繪圖, 1=Raw, 2=Filt+Interp, 3=Smooth+Filt+Interp
    "vector_color": "lime",      # 向量顏色
    "quiver_factor": 5.0,        # 向量縮放因子
    "grid_skip": 1,              # 網格跳過
    
    # 效能選項
    "compute_mode": "cpu",       # "cpu" | "cpu_parallel"
    "num_workers": None,         # None = auto (physical cores)
    "output_format": "npz",      # "npz" | "raw" | "mat" | "flo"
}

# ========== PIV 分析設定 (對應 a1) ==========
PIV_SETTINGS = {
    "int_area_1": 64,             # 第一次 pass 的 interrogation window
    "int_area_2": 32,             # 第二次 pass
    "int_area_3": "none",         # 第三次 pass
    "int_area_4": "none",         # 第四次 pass
    "int_area_5": "none",         # 第五次 pass
    "int_area_6": "none",         # 第六次 pass
    "overlap": 0.5,             # 重疊比例
    "sub_pix_method": 2,          # 1=3-pt Gauss, 2=2D Gauss
    "mask": None,               # 遮罩 (None 或 polygon 座標)
    "roi": None,                # ROI [x, y, width, height] 或 None
    "window_deform": "linear",   # "linear" 或 "spline"
    "invert_gray": False,        # 反轉灰階
    "repeat_corr": False,        # 重複相關 (4 次乘積)
    "disable_autocorr": True,    # 關閉第一次 pass 的自相關
    "corr_style": 1,             # 0=circular, 1=linear correlation
}

# ========== 後處理設定 (對應 a3) ==========
POSTPROC_SETTINGS = {
    "enable_vel_limit": True,    # 啟用速度限制
    "u_min": -64,                # 最小允許的 u 速度
    "u_max": 64,                 # 最大允許的 u 速度
    "v_min": -64,                # 最小允許的 v 速度
    "v_max": 64,                 # 最大允許的 v 速度
    "thres_std": 3.0,            # 標準差閾值 (-1=關閉)
    "thres_median": 2.5,         # 中值閾值 (-1=關閉)
    "thres_global": 5.0,         # 全域閾值 (-1=關閉)
    "interp_method": 2,          # -1=關閉, 1=Linear, 2=Cubic, 3=Kriging
    "smooth_data": True,         # 啟用平滑
}

# ========== SERVICE / 格式轉換設定 ==========
CONVERT_SETTINGS = {
    "input_mode": "none",      # "none" | "dir" | "files"
    "input_dir": "",           # 輸入目錄 (mode=dir)
    "input_files": [],         # 輸入檔案清單 (mode=files)
    "output_dir": "",
    "output_fmt": "mat",
}

# ========== 支援的影像格式 ==========
SUPPORTED_IMAGE_FORMATS = [".bmp", ".tif", ".tiff", ".jpg", ".jpeg", ".png"]

# ========== 向量結果格式 ==========
VECTOR_FILE_FORMATS = [".npz", ".mat", ".raw", ".flo"]

# ========== VIEWER 設定 ==========
VIEWER_SETTINGS = {
    # 檔案選取 (VIEWER 獨立於基本設定)
    "image_dir": "",                 # 圖像目錄 (背景影像來源)
    "vector_dir": "",                # 向量目錄 (結果檔來源)

    "current_pair": 1,
    "display_mode": "向量",          # "影像" | "向量" | "渦度"

    # 向量繪圖
    "vector_color": "lime",
    "grid_skip": 1,
    "quiver_factor": 5.0,
    "colorbar_enabled": False,       # False=單色, True=多色
    "colorbar_cmap": "turbo",
    "colorbar_range_mode": "Auto",   # "Auto" | "Manual"
    "colorbar_min": 0.0,
    "colorbar_max": 10.0,

    # 渦度繪圖
    "vorticity_method": "Central Difference",  # 顯示名稱
    "vort_cmap": "seismic",
    "vort_colorbar_range_mode": "Auto",
    "vort_colorbar_min": -5.0,
    "vort_colorbar_max": 5.0,
}

# ========== 效能參數 ==========
PERFORMANCE_SETTINGS = {
    "fft_chunk_size": 1024,
    "multipass_smooth_sigma": 1.5,
    "spline_order": 3,
    "autocorr_sigma": 1.5,
}
