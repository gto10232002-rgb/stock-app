import streamlit as st
import pandas as pd
import requests
import datetime
import time

# 頁面配置
st.set_page_config(page_title="台股籌碼選股器", layout="wide")
st.markdown("### 📊 台股籌碼選股")

@st.cache_data(ttl=3600)
def get_stock_data():
    # 1. 下載股價資料
    url_price = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res_price = requests.get(url_price, timeout=20)
    df_price = pd.DataFrame()
    if res_price.status_code == 200:
        raw_price = pd.DataFrame(res_price.json())
        df_price = raw_price[raw_price['Code'].str.len() == 4].copy()
        df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
        df_price = df_price[['Code', 'Name', 'price', 'vol']].rename(columns={'Code': 'code', 'Name': 'name'})

    # 2. 下載籌碼資料
    df_chips = pd.DataFrame()
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(7):
        date_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = "https://www.twse.com.tw/rwd/zh/fund/T86?date=" + date_str + "&selectType=ALLBUT0999&response=json"
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code == 200 and "data" in res.json():
            data = res.json()["data"]
            fields = res.json()["fields"]
            df_raw = pd.DataFrame(data, columns=fields)
            df_raw.columns = df_raw.columns.str.strip()
            fi_col = [c for c in df_raw.columns if '外資' in c and '買賣超股數' in c][0]
            it_col = [c for c in df_raw.columns if '投信' in c and '買賣超股數' in c][0]
            df_chips['code'] = df_raw['證券代號'].astype(str).str.strip()
            df_chips['fi'] = pd.to_numeric(df_raw[fi_col].str.replace(',', ''), errors='coerce') / 1000
            df_chips['it'] = pd.to_numeric(df_raw[it_col].str.replace(',', ''), errors='coerce') / 1000
            break
        time.sleep(0.5)

    df = pd.merge(df_price, df_chips, on='code', how='inner')
    df['chip_ratio'] = ((df['fi'] + df['it']) / df['vol'] * 100).round(2)
    return df

# 主邏輯區塊
try:
    df = get_stock_data()
    st.sidebar.header("篩選條件")
    min_p = st.sidebar.number_input("最低股價", value=0.0)
    max_p = st.sidebar.number_input("最高股價", value=100.0)
    min_v = st.sidebar.number_input("最低成交量(張)", value=1000)
    min_c = st.sidebar.slider("最低籌碼集中度(%)", -50, 50, 5)
    
    # 篩選
    res = df[(df['price'] >= min_p) & (df['price'] <= max_p) & 
             (df['vol'] >= min_v) & (df['chip_ratio'] >= min_c)].copy()
    res = res.sort_values(by='chip_ratio', ascending=False)
    
    # 建立合併欄位：網址 + " " + 顯示文字 (代號 名稱)
    # 這樣設定後，我們可以用 Regex 抓取空格
