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
# Page config + CSS (修正完成)
# ==========================================
st.set_page_config(page_title="StockTool", layout="wide")

st.markdown(
    "<style>"
    ".block-container {"
    "  padding-top: 3.6rem !important;"
    "  padding-bottom: 1.2rem !important;"
    "  padding-left: 0.8rem !important;"
    "  padding-right: 0.8rem !important;"
    "  max-width: 1200px;"
    "}"
    "h1, h2, h3 {"
    "  margin-top: 0rem !important;"
    "  margin-bottom: 0.6rem !important;"
    "}"
    "@media (max-width: 768px) {"
    "  .block-container {"
    "    padding-top: 4.6rem !important;"
    "    padding-left: 0.6rem !important;"
    "    padding-right: 0.6rem !important;"
    "  }"
    "}"
    "</style>",
    unsafe_allow_html=True
)

st.markdown("## 📊 台股多元策略選股系統")
st.caption("手機優先版｜先設定條件，再按「開始分析」")


# ==========================================
# Constants
# ==========================================
IND_MAP = {
    "24": "半導體業",
    "25": "電腦及週邊設備業",
    "26": "光電業",
    "27": "通信網路業",
    "28": "電子零組件業"
}

ETF_DB = {
    "2330": ["0050", "00919", "00929"],
    "2317": ["0050", "00919", "00929"],
    "2454": ["0050", "0056", "00878"]
}

BASE_CACHE_TTL = 3600
TECH_CACHE_TTL = 900


# ==========================================
# HTTP helpers
# ==========================================
@st.cache_resource
def get_http_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5)
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    return s


def safe_num(x):
    return pd.to_numeric(x.astype(str).str.replace(",", "", regex=False), errors="coerce")


# ==========================================
# Base data
# ==========================================
@st.cache_data(ttl=BASE_CACHE_TTL)
def get_data():
    s = get_http_session()

    price = s.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL").json()
    pe = s.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL").json()
    ind = s.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L").json()

    df = pd.DataFrame(price)
    df = df[df["Code"].str.len() == 4]

    df["price"] = safe_num(df["ClosingPrice"])
    df["vol"] = safe_num(df["TradeVolume"]) / 1000
    df["trade_value"] = safe_num(df["TradeValue"])

    df = df.rename(columns={"Code": "code", "Name": "name"})

    df_pe = pd.DataFrame(pe)[["Code", "PEratio"]]
    df_pe.columns = ["code", "pe"]
    df_pe["pe"] = safe_num(df_pe["pe"])

    df_ind = pd.DataFrame(ind)[["公司代號", "產業別"]]
    df_ind.columns = ["code", "industry"]
    df_ind["industry"] = df_ind["industry"].map(IND_MAP).fillna("其他")

    df = df.merge(df_pe, on="code", how="left")
    df = df.merge(df_ind, on="code", how="left")

    df["value_billion"] = df["trade_value"] / 1e8

    return df


# ==========================================
# Tech (簡化版)
# ==========================================
@st.cache_data(ttl=TECH_CACHE_TTL)
def get_tech(code):
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
# Main
# ==========================================
df = get_data()

with st.form("filter"):
    min_p = st.number_input("最低股價", value=0.0)
    max_p = st.number_input("最高股價", value=500.0)
    min_v = st.number_input("最低成交量", value=1000)

    submitted = st.form_submit_button("開始分析")

if not submitted:
    st.stop()

res = df[(df["price"] >= min_p) & (df["price"] <= max_p) & (df["vol"] >= min_v)].copy()

