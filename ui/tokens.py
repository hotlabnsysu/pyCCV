# -*- coding: utf-8 -*-
"""pyCCV UI 設計 token - 所有視覺常數的單一來源。

任何新的尺寸/色/字級常數皆應在此集中定義，避免散落於各 tab 檔案造成
視覺不一致。命名約定：
  - 尺寸：FIELD_H、INPUT_SM/MD/LG、SLIDER_W、LABEL_GAP、ROW_SPACING、CARD_SPACING
  - Margin：CARD_MARGIN、OUTER_MARGIN (皆為 (l, t, r, b) 四元組)
  - 色：HINT_FG、MUTED_FG、WARN_FG、OK_FG
  - 字級：FONT_BODY、FONT_HEADER、FONT_HINT、FONT_TAB
"""

# ── 尺寸 ────────────────────────────────────────────────────────────────
FIELD_H = 22            # 輸入元件統一高度
LABEL_GAP = 6           # label 與輸入元件之間的水平間距
ROW_SPACING = 5         # 卡片內同一區塊內各列的垂直間距
CARD_SPACING = 5        # 外層 (tab) 卡片之間的垂直間距

CARD_MARGIN = (10, 6, 10, 8)   # (left, top, right, bottom)
OUTER_MARGIN = (4, 4, 4, 4)

# 輸入寬度階梯 (三階)
INPUT_SM = 80    # 2-3 位數 spin: 第幾對 / 間隔大小 / CPU workers / 輸出格式
INPUT_MD = 106   # 一般 combo/spin: 峰值擬合 / 窗格變形 / 重疊比例 / 濾波閾值 / 向量顏色 / 色盤
INPUT_LG = 150   # 長枚舉文字 combo: 渦度方法 / 渦度色盤

SLIDER_W = 100
RANGE_EDIT_W = 52   # 小型數字輸入 (Min/Max colorbar range)

# ── 色 token ─────────────────────────────────────────────────────────────
HINT_FG = "#64748B"     # 次要提示文字 (建議值、單位說明)
MUTED_FG = "#858585"    # 停用/placeholder
WARN_FG = "#E6A020"     # 警告 (偵測失敗、格式不符)
OK_FG = "#EAEAEA"       # 成功 (偵測結果白色主文字)

# ── 字級 ────────────────────────────────────────────────────────────────
FONT_BODY = 13
FONT_HEADER = 13   # 卡片標題 (原 12px, 提升以強化層級)
FONT_HINT = 12     # 次要提示 (原 11px)
FONT_TAB = 12      # 頁籤按鈕 (原 11px)
