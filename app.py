import streamlit as st
import pandas as pd
import requests
import datetime
import time

st.set_page_config(page_title="台股籌碼選股器", layout="wide")
st.markdown("### 📊 台股籌碼選股")

@st.cache_data(ttl=3600)
def get_stock_data():
    # 1. 股價資料
    twse_price_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res_price = requests.get(twse_price_url, timeout=20)
    df_price_clean = pd.DataFrame()
    if res_price.status_code == 200:
        df_price = pd.DataFrame(res_price.json())
        df_price = df_price[df_price['Code'].str.len() == 4].copy()
        df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
        df_price_clean = df_price[['Code', 'Name', 'price', 'vol']].rename(columns={'Code': 'code', 'Name': 'name'})

    # 2. 籌碼資料
    df_chips_clean = pd.DataFrame()
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
            code_col = '證券代號'
            fi_col = [c for c in df_raw.columns if '外資' in c and '買賣超股數' in c][0]
            it_col = [c for c in df_raw.columns if '投信' in c and '買賣超股數' in c][0]
            df_chips_clean = pd.DataFrame()
            df_chips_clean['code'] = df_raw[code_col].astype(str).str.strip()
            df_chips_clean['fi'] = pd.to_numeric(df_raw[fi_col].str.replace(',', ''), errors='coerce') / 1000
            df_chips_clean['it'] = pd.to_numeric(df_raw[it_col].str.replace(',', ''), errors='coerce') / 1000
            break
        time.sleep(1)

    df = pd.merge(df_price_clean, df_chips_clean, on='code', how='inner')
    df['chip_ratio'] = (df['fi'] + df['it']) / df['vol'] * 100
    return df

try:
    df = get_stock_data()
    st.sidebar.header("篩選條件")
    min_p = st.sidebar.number_input("最低股價", value=0.0)
    max_p = st.sidebar.number_input("最高股價", value=100.0)
    min_v = st.sidebar.number_input("最低成交量(張)", value=1000)
    min_c = st.sidebar.slider("最低籌碼集中度(%)", -50, 50, 5)
    
    # 篩選
    res = df[(df['price']>=min_p) & (df['price']<=max_p) & (df['vol']>=min_v) & (df['chip_ratio']>=min_c)].copy()
    res = res.sort_values(by='chip_ratio', ascending=False)
    
    # 格式化顯示用 DataFrame
    display_df = res.copy()
    display_df['股價'] = display_df['price'].map('{:.2f}'.format)
    display_df['集中度%'] = display_df['chip_ratio'].map('{:.2f}'.format)
    
    # K線連結 (使用 HTML 顯示圖示)
    display_df['K線'] = display_df['code'].apply(lambda x: f'<a href="https://tw.stock.yahoo.com/quote/{x}" target="_blank">📈看K線</a>')
    
    st.write(f"📈 符合條件：{len(display_df)} 檔")
    
    # 最終呈現
    final_table = display_df.rename(columns={'code':'代號', 'name':'名稱'})[['代號', '名稱', '股價', '集中度%', 'K線']]
    st.write(final_table.to_html(escape=False, index=False), unsafe_allow_html=True)

except Exception as e:
    st.error(f"執行錯誤: {e}")
