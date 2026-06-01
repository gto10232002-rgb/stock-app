import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
import yfinance as yf

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed


# ==========================================
# 0. 頁面設定 / 手機安全 Padding（✅ 修正重點）
# ==========================================
st.set_page_config(
    page_title="StockTool",
    layout="wide",
)

st.markdown(
    "<style>"
    ".block-container {"
    "    padding-top: 3.6rem !important;"   /* ✅ 修正：避免標題被擋 */
    "    padding-bottom: 1.2rem !important;"
    "    padding-left: 0.8rem !important;"
    "    padding-right: 0.8rem !important;"
    "    max-width: 1200px;"
    "}"
    "h1, h2, h3 {"
    "    margin-top: 0rem !important;"
    "    margin-bottom: 0.6rem !important;"
    "}"
    "@media (max-width: 768px) {"
    "    .block-container {"
    "        padding-top: 4.6rem !important;"  /* ✅ 手機額外保險 */
    "        padding-left: 0.6rem !important;"
    "        padding-right: 0.6rem !important;"
    "    }"
    "}"
    "</style>",
    unsafe_allow_html=True
)

st.markdown("## 📊 台股多元策略選股系統")
st.caption("手機優先版｜先設定條件，再按「開始分析」")


# ==========================================
# 1. 常數設定（以下邏輯皆與前版相同）
# ==========================================
IND_MAP = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "07": "化學工業", "08": "生技醫療業",
    "09": "玻璃陶瓷", "10": "造紙工業", "11": "鋼鐵工業", "12": "橡膠工業",
    "13": "汽車工業", "14": "建材營建", "15": "航運業", "16": "觀光餐旅",
    "17": "金融保險", "18": "貿易百貨", "19": "綜合業", "20": "其他業",
    "21": "化學工業", "22": "生技醫療業", "23": "油電燃氣業", "24": "半導體業",
    "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業",
    "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業",
    "31": "其他電子業", "35": "綠能環保", "36": "數位雲端",
    "37": "運動休閒", "38": "居家生活", "91": "存託憑證"
}

# ✅ ETF_DB 請保留你現有那份（此處略，與上一版完全相同）
ETF_DB = { **你的完整 ETF_DB 保持不變** }

BASE_CACHE_TTL = 3600
TECH_CACHE_TTL = 900
YF_CHUNK_SIZE = 30
MAX_ANALYZE_DEFAULT = 120
T86_LOOKBACK_DAYS = 7

# ==========================================
# ✅ 以下「資料抓取 / 策略 / 加速 / 卡片顯示」
# ✅ 與我上一版提供內容 **完全一致**
# ✅ 不影響本次 UI 修正
# ==========================================

# ⚠️（篇幅考量）
# 👉 從這裡開始，請 **完整保留你目前 app.py 中**
# 👉 「HTTP session → 資料抓取 → 技術指標 → 策略 → 卡片顯示 → 主程式」
# 👉 內容一字不改即可
