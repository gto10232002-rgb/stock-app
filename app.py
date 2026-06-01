import streamlit as st
import pandas as pd
import requests
import datetime
import time
import yfinance as yf

# ==========================================
# 1. 頁面配置
# ==========================================
st.set_page_config(page_title="StockTool", layout="wide")

st.markdown(
    "<style>"
    ".block-container {"
    "  padding-top: 3.6rem !important;"
    "  padding-bottom: 0rem !important;"
    "}"
    "@media (max-width: 768px) {"
    "  .block-container {"
    "    padding-top: 4.6rem !important;"
    "  }"
    "}"
    "</style>",
    unsafe_allow_html=True
)

st.markdown("### 📊 台股多元策略選股系統")

# ==========================================
# 2. 基礎資料
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_base_data():
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        data = requests.get(url, timeout=20).json()
        df = pd.DataFrame(data)

        df = df[df["Code"].str.len() == 4].copy()

        df["price"] = pd.to_numeric(df["ClosingPrice"].str.replace(",", ""), errors="coerce")
        df["vol"] = pd.to_numeric(df["TradeVolume"].str.replace(",", ""), errors="coerce") / 1000

        df = df.rename(columns={"Code": "code", "Name": "name"})

        return df

    except Exception as e:
        st.error(f"資料抓取失敗: {e}")
        return pd.DataFrame()

# ==========================================
# 技術指標
# ==========================================
@st.cache_data(ttl=600)
def get_single_stock_tech(code):
    try:
        hist = yf.download(f"{code}.TW", period="1mo", progress=False)

        if hist.empty or len(hist) < 2:
            return 0.0, 0.0

        closes = hist["Close"].dropna()
        highs = hist["High"].dropna()

        if len(closes) < 2:
            return 0.0, 0.0

        high_1m = highs.max()
        current = closes.iloc[-1]
        prev = closes.iloc[-2]

        dd = 0.0
        chg = 0.0

        if high_1m > 0:
            dd = (high_1m - current) / high_1m * 100

        if prev > 0:
            chg = (current - prev) / prev * 100

        return round(dd, 2), round(chg, 2)

    except:
        return 0.0, 0.0

# ==========================================
# 主程式
# ==========================================
df = get_stock_base_data()

if df.empty:
    st.warning("無法取得資料")
    st.stop()

# Sidebar
st.sidebar.header("篩選條件")

min_p = st.sidebar.number_input("最低股價", value=0.0)
max_p = st.sidebar.number_input("最高股價", value=500.0)
min_v = st.sidebar.number_input("最低成交量", value=1000)

# ✅ 正確條件（已修正）
res = df[
    (df["price"] >= min_p) &
    (df["price"] <= max_p) &
    (df["vol"] >= min_v)
].copy()

if res.empty:
    st.warning("沒有符合條件的股票")
    st.stop()

# 技術分析
st.info(f"開始分析 {len(res)} 檔股票")

drawdown = []
change = []

progress = st.progress(0)

for i, code in enumerate(res["code"]):
    dd, chg = get_single_stock_tech(code)
    drawdown.append(dd)
    change.append(chg)
    progress.progress((i + 1) / len(res))
    time.sleep(0.01)

progress.empty()

res["回檔%"] = drawdown
res["今日漲幅%"] = change

res = res.sort_values(by="今日漲幅%", ascending=False)

st.success(f"符合條件：{len(res)} 檔")

st.dataframe(
    res[["code", "name", "price", "vol", "今日漲幅%", "回檔%"]],
    use_container_width=True,
    height=600
)
