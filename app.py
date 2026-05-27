import streamlit as st
import pandas as pd
import requests
import datetime
import time

# 頁面設定
st.set_page_config(page_title="台股籌碼選股器", layout="wide")
st.title("📊 台股籌碼選股工具")

# 數據獲取函式
@st.cache_data(ttl=3600)
def get_stock_data():
    # 1. 下載股價
    twse_price_url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res_price = requests.get(twse_price_url, timeout=20)
    df_price_clean = pd.DataFrame()
    if res_price.status_code == 200:
        df_price = pd.DataFrame(res_price.json())
        df_price = df_price[df_price['Code'].str.len() == 4].copy()
        df_price['收盤價'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df_price['當日成交量(張)'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
        df_price_clean = df_price[['Code', 'Name', '收盤價', '當日成交量(張)']].rename(columns={'Code': '股票代碼', 'Name': '股票名稱'})

    # 2. 下載籌碼
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
            df_temp['股票代碼'] = df_raw[col_code].astype(str).str.strip()
            df_temp['外資買超(張)'] = pd.to_numeric(df_raw[fi_col].str.replace(',', ''), errors='coerce') / 1000
            df_temp['投信買超(張)'] = pd.to_numeric(df_raw[it_col].str.replace(',', ''), errors='coerce') / 1000
            df_chips_clean = df_temp
            break
        time.sleep(1)

    # 3. 數據融合
    final_df = pd.merge(df_price_clean, df_chips_clean, on='股票代碼', how='inner')
    final_df['主力買超(張)'] = final_df['外資買超(張)'] + final_df['投信買超(張)']
    final_df['籌碼集中度(%)'] = (final_df['主力買超(張)'] / final_df['當日成交量(張)'] * 100).round(2)
    return final_df

# 載入與篩選
try:
    df = get_stock_data()
    
    st.sidebar.header("🔍 篩選條件")
    min_price = st.sidebar.number_input("最低股價", value=0.0)
    max_price = st.sidebar.number_input("最高股價", value=100.0)
    min_vol = st.sidebar.number_input("最低成交量 (張)", value=1000)
    min_chip = st.sidebar.slider("最低籌碼集中度 (%)", -50, 50, 5)
    
    filtered_df = df[(df['收盤價'] >= min_price) & (df['收盤價'] <= max_price) & 
                     (df['當日成交量(張)'] >= min_vol) & (df['籌碼集中度(%)'] >= min_chip)]
    
    sort_by = st.sidebar.selectbox("排序基準", ["籌碼集中度(%)", "當日成交量(張)", "外資買超(張)", "投信買超(張)"])
    filtered_df = filtered_df.sort_values(by=sort_by, ascending=False)
    
    # 顯示優化
    st.write(f"📊 共 {len(filtered_df)} 檔股票符合條件")
    
    # 建立 K 線連結欄位
    display_df = filtered_df.copy()
    display_df['K線'] = display_df['股票代碼'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
    
    # 篩選要在手機上顯示的欄位，強制使用 st.table 以適應手機寬度
    cols_to_show = ['股票代碼', '股票名稱', '收盤價', '籌碼集中度(%)', 'K線']
    
    # 轉換顯示：將 URL 轉為簡單的文字連結，確保 table 顯示美觀
    table_df = display_df[cols_to_show].copy()
    
    # 使用 Markdown 語法產生連結，在 st.table 中顯示會更乾淨
    table_df['K線'] = table_df.apply(lambda row: f"[📈看K線]({row['K線']})", axis=1)
    
    # 顯示靜態表格
    st.table(table_df.head(30)) 

except Exception as e:
    st.error(f"資料讀取錯誤: {e}")
