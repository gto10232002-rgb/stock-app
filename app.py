import streamlit as st
import pandas as pd
import requests
import datetime
import time
import yfinance as yf

# 頁面配置
st.set_page_config(page_title="StockTool", layout="wide")

st.markdown("""
<style>
    .block-container {
        padding-top: 2.8rem !important; 
        padding-bottom: 0rem !important;
    }
    h3 {
        margin-top: 0rem !important;
        margin-bottom: 0.4rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📊 台股多元策略選股系統")

@st.cache_data(ttl=3600)
def get_stock_base_data():
    # A. 🛡️ 取得每日收盤行情 (安全防護版)
    df_price = pd.DataFrame()
    try:
        url_price = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        res_price = requests.get(url_price, timeout=20)
        if res_price.status_code == 200:
            data_json = res_price.json()
            if isinstance(data_json, list) and len(data_json) > 0:
                raw_price = pd.DataFrame(data_json)
                if all(col in raw_price.columns for col in ['Code', 'ClosingPrice', 'TradeVolume', 'TradeValue', 'Name']):
                    df_price = raw_price[raw_price['Code'].str.len() == 4].copy()
                    df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
                    df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
                    df_price['trade_value'] = pd.to_numeric(df_price['TradeValue'].str.replace(',', ''), errors='coerce')
                    df_price = df_price[['Code', 'Name', 'price', 'vol', 'trade_value']].rename(columns={'Code': 'code', 'Name': 'name'})
    except Exception:
        pass

    # B. 🛡️ 取得本益比資料 (安全防護版)
    df_pe = pd.DataFrame()
    try:
        url_pe = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
        res_pe = requests.get(url_pe, timeout=20)
        if res_pe.status_code == 200:
            data_json = res_pe.json()
            if isinstance(data_json, list) and len(data_json) > 0:
                raw_pe = pd.DataFrame(data_json)
                if 'Code' in raw_pe.columns and 'PEratio' in raw_pe.columns:
                    df_pe = raw_pe[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
                    df_pe['pe'] = pd.to_numeric(df_pe['pe'].str.replace(',', ''), errors='coerce')
    except Exception:
        pass

    # C. 🛡️ 取得產業別對照 (安全防護版)
    df_ind = pd.DataFrame()
    try:
        url_industry = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        res_ind = requests.get(url_industry, timeout=20)
        if res_ind.status_code == 200:
            data_json = res_ind.json()
