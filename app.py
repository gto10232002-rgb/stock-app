import streamlit as st
import pandas as pd
import requests
import datetime
import time

st.set_page_config(page_title="Stock Tool", layout="wide")
st.markdown("### 📊 台股籌碼選股")

@st.cache_data(ttl=3600)
def get_stock_data():
    twse_price_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res_price = requests.get(twse_price_url, timeout=20)
    df_price_clean = pd.DataFrame()
    if res_price.status_code == 200:
        df_price = pd.DataFrame(res_price.json())
        df_price = df_price[df_price['Code'].str.len() == 4].copy()
        df_price['收盤價'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df_price['當日成交量(張)'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
        df_price_clean = df_price[['Code', 'Name', '收盤價', '當日成交量(張)']].rename(columns={'Code': '代號', 'Name': '名稱'})

    df_chips_clean = pd.DataFrame()
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(7):
        target_date = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={target_date}&selectType=ALLBUT0999&response=json"
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code == 200 and "data" in res.json():
            data = res.json()["data"]
            fields = res.json()["fields"]
            df_raw = pd.DataFrame(data, columns=fields)
            df_raw.columns = df_raw.columns.str.strip()
            col_code = '證券代號'
            fi_col = [c for c in df_raw.columns if '外資' in c and '買賣超股數' in c][0]
            it_col = [c for c in df_raw.columns if '投信' in c and '買賣超股數' in c][0]
            df_temp = pd.DataFrame()
            df_temp['代號'] = df_raw[col_code].astype(str).str.strip()
            df_temp['外資買超(張)'] = pd.to_numeric(df_raw[fi_col].str.replace(',', ''), errors='coerce') / 1000
            df_temp['投信買超(張)'] = pd.to_numeric(df_raw[it_col].str.replace(',', ''), errors='coerce') / 1000
            df_chips_clean = df_temp
            break
        time.sleep(1)

    final_df = pd.merge(df_price_clean, df_chips_clean, on='代號', how='inner')
    final_df['主力買超(張)'] = final_df['外資買超(張)'] + final_df['投信買超(張)']
    final_df['集中度%'] = (final_df['主力買超(張)'] / final_df['當日成交量(張)'] * 100)
    return final_df

try:
    df = get_stock_data()
    st.sidebar.header("篩選條件")
    min_price = st.sidebar.number_input("最低股價", value=0.0)
    max_price = st.sidebar.number_input("最高股價", value=100.0)
    min_vol = st.sidebar.number_input("最低量(張)", value=1000)
    min_chip = st.sidebar.slider("最低集中度(%)", -50, 50, 5)
    
    filtered_df = df[(df['收盤價'] >= min_price) & (df['收盤價'] <= max_price) & (df['當日成交量(張)'] >= min_vol) & (df['集中度%'] >= min_chip)].copy()
    
    filtered_df['股價'] = filtered_df['收盤價'].round(2)
    filtered_df['集中度%'] = filtered_df['集中度%'].round(2)
    
    sort_by = st.sidebar.selectbox("排序", ["集中度%", "當日成交量(張)"])
    filtered_df = filtered_df.sort_values(by=sort_by, ascending=False)
    
    st.write(f"符合筆數: {len(filtered_df)}")
    
    filtered_df['K線'] = filtered_df['代號'].apply(lambda x: f
