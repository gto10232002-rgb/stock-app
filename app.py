import streamlit as st
import pandas as pd
import requests
import datetime
import time
import yfinance as yf


# ==========================================
# 1. 頁面配置與 CSS（已修正）
# ==========================================
st.set_page_config(page_title="StockTool", layout="wide")

st.markdown(
    "<style>"
    ".block-container {"
    "  padding-top: 3.6rem !important;"
    "  padding-bottom: 0rem !important;"
    "}"
    "h3 {"
    "  margin-top: 0rem !important;"
    "  margin-bottom: 0.4rem !important;"
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
def get_stock_base_data_v3():

    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    data = requests.get(url).json()
    df = pd.DataFrame(data)

    df = df[df["Code"].str.len() == 4]

    df["price"] = pd.to_numeric(df["ClosingPrice"].str.replace(",", ""), errors="coerce")
    df["vol"] = pd.to_numeric(df["TradeVolume"].str.replace(",", ""), errors="coerce") / 1000

    df = df.rename(columns={"Code": "code", "Name": "name"})

    return df


# ==========================================
# 技術指標
# ==========================================
@st.cache_data(ttl=600)
def get_single_stock_tech(code):
    try:
        df = yf.download(f"{code}.TW", period="1mo", progress=False)

        if len(df) < 2:
            return 0, 0

        high = df["High"].max()
        cur = df["Close"].iloc[-1]
        prev = df["Close"].iloc[-2]

        dd = (high - cur) / high * 100 if high > 0 else 0
        chg = (cur - prev) / prev * 100 if prev > 0 else 0

        return round(dd, 2), round(chg, 2)
    except:
        return 0, 0


# ==========================================
# 3. 主程式
# ==========================================
df = get_stock_base_data_v3()

st.sidebar.header("條件")

min_p = st.sidebar.number_input("最低股價", value=0.0)
max_p = st.sidebar.number_input("最高股價", value=500.0)
min_v = st.sidebar.number_input("最低成交量", value=1000)

# ✅ 重點：這裡已修正 (> < 不再是 HTML entity)
res = df[(df["price"] >= min_p) & (df["price"] <= max_p) & (df["vol"] >= min_v)].copy()

if res.empty:
    st.warning("沒有符合條件")
    st.stop()

st.info(f"開始分析 {len(res)} 檔...")

drawdown = []
change = []

for code in res["code"]:
    dd, chg = get_single_stock_tech(code)
    drawdown.append(dd)
    change.append(chg)

res["回檔%"] = drawdown
res["漲幅%"] = change

res = res.sort_values(by="漲幅%", ascending=False)

st.success(f"符合條件：{len(res)} 檔")

st.dataframe(
