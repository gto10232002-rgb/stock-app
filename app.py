import streamlit as st
import pandas as pd
import requests
import datetime
import time

st.set_page_config(page_title="台股籌碼選股器", layout="wide")
st.markdown("### 📊 台股籌碼選股")

@st.cache_data(ttl=3600)
def get_stock_data():
    twse_price_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res_price = requests.get(twse_price_url, timeout=20)
    df_price_clean = pd.DataFrame()
    if res_price.status_code == 200:
        df_price = pd.DataFrame(res_price.json())
        df_price = df_price[df_price['Code'].str.len() == 4].copy()
        df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
        df_price_clean = df_price[['Code', 'Name', 'price', 'vol']].rename(columns={'Code': 'code', 'Name': 'name'})

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
    st.sidebar.header("篩選條件")
    min_p = st.sidebar.number_input("最低股價", value=0.0)
    max_p = st.sidebar.number_input("最高股價", value=100.0)
    min_v = st.sidebar.number_input("最低成交量(張)", value=1000)
    min_c = st.sidebar.slider("最低籌碼集中度(%)", -50, 50, 5)
    
    # 篩選數據
    res = df[(df['price']>=min_p) & (df['price']<=max_p) & (df['vol']>=min_v) & (df['chip_ratio']>=min_c)].copy()
    res = res.sort_values(by='chip_ratio', ascending=False)
    
    # 欄位格式化 (確保數值已四捨五入到小數點後兩位)
    res['股價'] = res['price'].round(2)
    res['集中度%'] = res['chip_ratio']
    res['K線'] = res['code'].apply(lambda x: "https://tw.stock.yahoo.com/quote/" + x)
    
    # 整理顯示欄位
    display_df = res.rename(columns={'code':'代號', 'name':'名稱'})[['代號', '名稱', '股價', '集中度%', 'K線']]
    
    st.write(f"📈 符合條件：{len(display_df)} 檔")
    
    # 使用 dataframe 顯示並啟用自動寬度，這能填滿版面
    st.dataframe(
        display_df,
        column_config={
            "K線": st.column_config.LinkColumn("個股資訊", display_text="📈查看"),
        },
        use_container_width=True,
        hide_index=True
    )

except Exception as e:
    st.error(f"執行錯誤: {e}")
