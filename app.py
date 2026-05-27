import streamlit as st
import pandas as pd
import requests
import datetime
import time

# 設定頁面寬度與佈局
st.set_page_config(page_title="台股籌碼選股器", layout="wide")
st.markdown("### 📊 台股籌碼選股")

@st.cache_data(ttl=3600)
def get_stock_data():
    # 簡化資料下載邏輯
    twse_price_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res_price = requests.get(twse_price_url, timeout=20)
    df_price_clean = pd.DataFrame()
    if res_price.status_code == 200:
        df_price = pd.DataFrame(res_price.json())
        df_price = df_price[df_price['Code'].str.len() == 4].copy()
        df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
        df_price_clean = df_price[['Code', 'Name', 'price', 'vol']].rename(columns={'Code': 'code', 'Name': 'name'})

    # 籌碼資料邏輯
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
    df['chip_ratio'] = ((df['fi'] + df['it']) / df['vol'] * 100).round(2)
    return df

try:
    df = get_stock_data()
    # 側邊欄篩選
    min_p, max_p = st.sidebar.number_input("最低股價", value=0.0), st.sidebar.number_input("最高股價", value=100.0)
    min_v = st.sidebar.number_input("最低成交量(張)", value=1000)
    min_c = st.sidebar.slider("最低籌碼集中度(%)", -50, 50, 5)
    
    res = df[(df['price']>=min_p) & (df['price']<=max_p) & (df['vol']>=min_v) & (df['chip_ratio']>=min_c)].copy()
    res = res.sort_values(by='chip_ratio', ascending=False)
    
    # 整合「個股資訊」欄位：合併代號與名稱，並加上 Yahoo 連結
    res['個股資訊'] = res.apply(lambda x: f"[{x['code']} {x['name']}](https://tw.stock.yahoo.com/quote/{x['code']})", axis=1)
    res['股價'] = res['price'].round(2)
    res['集中度%'] = res['chip_ratio']
    
    st.write(f"📈 符合條件：{len(res)} 檔")
    
    # 使用 st.dataframe 的 markdown 渲染功能，將超連結整合進表格
    st.dataframe(
        res[['個股資訊', '股價', '集中度%']],
        column_config={
            "個股資訊": st.column_config.TextColumn("代號/名稱 (點擊看K線)", help="點擊可前往Yahoo股市"),
            "股價": st.column_config.NumberColumn(format="%.2f"),
            "集中度%": st.column_config.NumberColumn(format="%.2f%%")
        },
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
