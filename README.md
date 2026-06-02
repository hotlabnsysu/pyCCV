# pyCCV

PIV (Particle Image Velocimetry) 分析工具

## 功能

- **Multi-pass FFT 互相關** — 最多 6 次 pass，支援子像素定位 (3-pt Gauss / 2D Gauss)、Window 變形 (Linear / Spline)、重複相關增強 (DDC)、自相關抑制
- **後處理** — 速度限制、標準差 / 中值 / 全域過濾、NaN 插值 (Linear / Cubic / Kriging)、加權平滑
- **多核心加速** — `scipy.fft.set_workers` 多執行緒 FFT；`ProcessPoolExecutor` 多程序影像對平行處理
- **結果檢視 (VIEW)** — 影像 / 向量 / 渦度三種模式，支援 Colorbar、多種渦度演算法 (CDM / Stokes / LSD)
- **格式轉換 (SERVICE)** — NPZ / MAT / FLO / RAW 雙向轉換
- **設定保存 / 載入** — 分析參數 JSON 匯出入

## 環境需求

- Windows 10+
- Python 3.10 / 3.11 / 3.12

## 安裝

```
雙擊 venv_setup.bat
```

腳本會自動偵測 Python、建立 venv、安裝所有套件。

## 啟動

```
venv\Scripts\activate
python main.py
```

## 專案結構

```
pyCCV/
├── main.py              # 程式入口
├── config.py            # 預設參數配置
├── core/                # PIV 演算核心
│   ├── piv_fft.py           # FFT 互相關 (單核)
│   ├── piv_fft_parallel.py  # 多核心包裝
│   ├── postprocess.py       # 後處理流程
│   ├── filters.py           # 向量過濾器
│   ├── interpolation.py     # NaN 插值
│   └── smooth.py            # 加權平滑
├── services/            # 業務邏輯層
│   ├── analysis.py          # 分析服務
│   ├── convert_service.py   # 格式轉換服務
│   ├── settings.py          # 設定管理
│   ├── vorticity.py         # 渦度計算
│   └── logger.py            # 日誌
├── shared/              # 共用模組
│   ├── io_formats.py        # NPZ/MAT/FLO/RAW I/O
│   └── settings_json.py     # 設定 JSON 序列化
├── ui/                  # PySide6-Essentials UI
│   ├── app.py               # 主視窗
│   ├── style.py             # VS Code Dark 主題
│   ├── controller.py        # 主控制器
│   ├── tabs/                # 分頁 (基本設定/PIV設定/VIEW/SERVICE)
│   └── components/          # 共用元件
├── utils/               # 工具函式
├── tests/               # pytest 測試
├── requirements.txt     # 套件相依
└── venv_setup.bat       # 一鍵建立虛擬環境
```

## 授權

MIT-style License — Non-Commercial — Research Use Only

Hydrodynamics & Ocean Technology Laboratory (HOTLAB), National Sun Yat-sen University
