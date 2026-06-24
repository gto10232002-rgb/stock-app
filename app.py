import streamlit as st
import pandas as pd
import requests
import datetime
import yfinance as yf
import numpy as np

# ==========================================
# 1. 頁面配置與 CSS 樣式微調
# ==========================================
st.set_page_config(page_title="StockTool", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.8rem !important; padding-bottom: 0rem !important; }
    h3 { margin-top: 0rem !important; margin-bottom: 0.4rem !important; }
    .stAlert { padding: 0.6rem !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📊 台股多元策略選股系統")
st.caption("📌 關盤資訊會在每日 18:30 之後導入")

# ==========================================
# 2. 💡 ETF 成分資料庫與名稱合併函數
# ==========================================
etf_db = {
    "2330": ["0050", "00919", "00929"], "2317": ["0050", "00919", "00929"], 
    "2454": ["0050", "0056", "00878", "00919", "00929", "00940"], "2308": ["0050", "00929"], 
    "3711": ["0050", "0056", "00878", "00919"], "2303": ["0050", "0056", "00878", "00919", "00929", "00940"],
    "2881": ["0050", "00878", "00919", "00940"], "2882": ["0050", "00878", "00919"], 
    "2891": ["0050", "0056", "00878", "00919", "00940"], "2382": ["0050", "0056", "00878", "00919", "00940"], 
    "2886": ["0050", "00878"], "3008": ["0050", "00919", "00929"], "2884": ["0050"], 
    "2885": ["0050", "00878", "00940"], "2892": ["0050", "00940"], 
    "2357": ["0050", "0056", "00878", "00919", "00929", "00940"], "3231": ["0050", "0056", "00878", "00929"], 
    "1216": ["0050", "0056", "00878", "00940"], "2412": ["0050", "00878"], "1301": ["0050"], 
    "1303": ["0050"], "2603": ["0050", "0056", "00878", "00919", "00940"], "3037": ["0050"],
    "2301": ["0050", "0056", "00878", "00929"], "4904": ["0050", "00878"], "2327": ["0050", "00919"], 
    "3045": ["0050", "00878", "00940"], "2408": ["0050"], "2449": ["0050", "0056", "00878"], 
    "2345": ["0050"], "2395": ["0050"], "2360": ["0050"], "2368": ["0050"], "3017": ["0050"], 
    "2383": ["0050"], "2207": ["0050"], "6669": ["0050"], "3653": ["0050"], "3661": ["0050"], 
    "2002": ["0050"], "5880": ["0050"], "2880": ["0050", "0056", "00878"], "2883": ["0050", "00940"],
    "2890": ["0050", "00940"], "6505": ["0050"], "6919": ["0050"], "7769": ["0050"], 
    "2059": ["0050"], "2344": ["0050"], "2376": ["0056", "00878"], 
    "2324": ["0056", "00878", "00919", "00929", "00940"], 
    "2356": ["0056", "00878", "00940"], "2385": ["0056", "00940"], 
    "3034": ["0056", "00878", "00919", "00929", "00940"], "3702": ["0056", "00940"],
    "4938": ["0056", "00929", "00940"], "3293": ["0056", "00878", "00940"], 
    "2474": ["0056", "00878", "00940"], "3005": ["0056", "00940"], "2379": ["0056", "00878", "00940"], 
    "2421": ["0056", "00940"], "6414": ["0056", "00940"], "3406": ["0056", "00919", "00940"],
    "2439": ["0056", "00940"], "6188": ["0056", "00940"], "6285": ["0056", "00940"], 
    "8016": ["0056", "00940"], "6139": ["0056", "00940"], "5269": ["0056", "00940"], 
    "6196": ["0056", "00940"], "6239": ["0056", "00919", "00929", "00940"], "4958": ["00878", "00919"], 
    "1402": ["00878"], "2912": ["00878", "00940"], "2609": ["00919"], "8209": ["00919"],
    "6488": ["00929", "00940"], "2801": ["00940"], "9904": ["00940"], "1102": ["00940"], 
    "4915": ["00940"], "2615": ["00940"], "1319": ["00940"], "3706": ["00940"], 
    "6176": ["00940"], "1513": ["00940"], "2393": ["00940"], "6257": ["00940"]
}

def merge_etf_info(row):
    c = str(row['code']).strip()
    base_name = str(row['name']).strip()
    if c in etf_db:
        labels = " ".join([f"[{e}]" for e in etf_db[c]])
        return f"{base_name} {labels}"
    return base_name

# ==========================================
# 3. 獲取台股基礎資料 (證交所 Open API)
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_base_data_final():
    cols = ['code', 'name', 'price', 'vol', 'trade_value', 'pe', 'industry', 'chip_ratio', 'value_billion']
    empty_df = pd.DataFrame(columns=cols)

    df_price = pd.DataFrame()
    try:
        res_p = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=15)
        if res_p.status_code == 200 and res_p.json():
            raw = pd.DataFrame(res_p.json())
            df_price = raw[raw['Code'].str.len() == 4].copy()
            df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
            df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
            df_price['trade_value'] = pd.to_numeric(df_price['TradeValue'].str.replace(',', ''), errors='coerce')
            df_price = df_price[['Code', 'Name', 'price', 'vol', 'trade_value']].rename(columns={'Code': 'code', 'Name': 'name'})
            df_price = df_price[~df_price['code'].str.startswith('91')] 
    except Exception as e:
        st.sidebar.error(f"⚠️ 股價API異常: {e}")

    if df_price.empty:
        return empty_df

    df_pe = pd.DataFrame()
    try:
        res_pe = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", timeout=15)
        if res_pe.status_code == 200 and res_pe.json():
            raw_pe = pd.DataFrame(res_pe.json())
            df_pe = raw_pe[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
            df_pe['pe'] = pd.to_numeric(df_pe['pe'].str.replace(',', ''), errors='coerce')
    except Exception:
        pass

    df_ind = pd.DataFrame()
    try:
        res_ind = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", timeout=15)
        if res_ind.status_code == 200 and res_ind.json():
            raw_ind = pd.DataFrame(res_ind.json())
            df_ind = raw_ind[['公司代號', '產業別']].rename(columns={'公司代號': 'code', '產業別': 'industry'})
    except Exception:
        pass

    df_chips = pd.DataFrame()
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(7):
        d_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d_str}&selectType=ALLBUT0999&response=json"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and "data" in res.json():
                js = res.json()
                if "fields" in js and "data" in js and js["data"]:
                    df_raw = pd.DataFrame(js["data"], columns=[c.strip() for c in js["fields"]])
                    fi_c = [c for c in df_raw.columns if '外資' in c and '買賣超' in c]
                    it_c = [c for c in df_raw.columns if '投信' in c and '買賣超' in c]
                    
                    if fi_c and it_c:
                        df_chips = pd.DataFrame()
                        df_chips['code'] = df_raw['證券代號'].astype(str).str.strip()
                        df_chips['fi'] = pd.to_numeric(df_raw[fi_c[0]].str.replace(',', ''), errors='coerce') / 1000
                        df_chips['it'] = pd.to_numeric(df_raw[it_c[0]].str
