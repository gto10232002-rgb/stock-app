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
    # A. 🛡️ 取得每日收盤行情
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

    # B. 🛡️ 取得本益比資料
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

    # C. 🛡️ 取得產業別對照
    df_ind = pd.DataFrame()
    try:
        url_industry = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        res_ind = requests.get(url_industry, timeout=20)
        if res_ind.status_code == 200:
            data_json = res_ind.json()
            if isinstance(data_json, list) and len(data_json) > 0:
                raw_ind = pd.DataFrame(data_json)
                if '公司代號' in raw_ind.columns and '產業別' in raw_ind.columns:
                    df_ind = raw_ind[['公司代號', '產業別']].rename(columns={'公司代號': 'code', '產業別': 'industry'})
                    
                    ind_map = {
                        "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
                        "05": "電機機械", "06": "電器電纜", "07": "化學工業", "08": "生技醫療業",
                        "09": "玻璃陶瓷", "10": "造紙工業", "11": "鋼鐵工業", "12": "橡膠工業",
                        "13": "汽車工業", "14": "建材营建", "15": "航運業", "16": "觀光餐旅",
                        "17": "金融保險", "18": "貿易百貨", "19": "綜合業", "20": "其他業",
                        "23": "油電燃氣業", "24": "半導體業", "25": "電腦及週邊設備業", 
                        "26": "光電業", "27": "通信網路業", "28": "電子零組件業", 
                        "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業",
                        "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活"
                    }
                    df_ind['industry'] = df_ind['industry'].astype(str).str.strip().map(ind_map).fillna(df_ind['industry'])
    except Exception:
        pass

    # D. 🛡️ 晶片籌碼撈取機制
    df_chips = pd.DataFrame()
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(7):
        date_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 200:
                res_json = res.json()
                if "data" in res_json and "fields" in res_json:
                    data = res_json["data"]
                    fields = res_json["fields"]
                    if data and fields:
                        df_raw = pd.DataFrame(data, columns=fields)
                        df_raw.columns = df_raw.columns.str.strip()
                        
                        fi_cols = [c for c in df_raw.columns if '外資' in c and '買賣超' in c]
                        it_cols = [c for c in df_raw.columns if '投信' in c and '買賣超' in c]
                        
                        if fi_cols and it_cols and '證券代號' in df_raw.columns:
                            fi_col = fi_cols[0]
                            it_col = it_cols[0]
                            df_chips = pd.DataFrame()
                            df_chips['code'] = df_raw['證券代號'].astype(str).str.strip()
                            df_chips['fi'] = pd.to_numeric(df_raw[fi_col].str.replace(',', ''), errors='coerce') / 1000
                            df_chips['it'] = pd.to_numeric(df_raw[it_col].str.replace(',', ''), errors='coerce') / 1000
                            break
        except Exception:
            pass
        time.sleep(0.3)

    if df_price.empty or df_chips.empty:
        return pd.DataFrame()
        
    df = pd.merge(df_price, df_chips, on='code', how='inner')
    
    if not df_pe.empty:
        df = pd.merge(df, df_pe, on='code', how='left')
    else:
        df['pe'] = pd.NA
        
    if not df_ind.empty:
        df = pd.merge(df, df_ind, on='code', how='left')
    else:
        df['industry'] = '其他'
        
    df['industry'] = df['industry'].fillna('其他')
    df['chip_ratio'] = ((df['fi'] + df['it']) / df['vol'] * 100).round(2)
    df['value_billion'] = (df['trade_value'] / 100000000).round(2)
    return df

try:
    with st.spinner("正在同步最新籌碼與產業數據..."):
        df = get_stock_base_data()
    
    if df.empty:
        st.warning("📅 暫時無法從證交所取得完整即時資料，請稍後再試。")
    else:
        st.sidebar.header("🎯 基礎篩選條件")
        min_p = st.sidebar.number_input("最低股價", value=0.0)
        max_p = st.sidebar.number_input("最高股價", value=500.0)
        min_v = st.sidebar.number_input("最低成交量(張)", value=1000)
        max_pe = st.sidebar.number_input("最高本益比 (0為不限)", value=30.0)
        
        target_industry = st.sidebar.selectbox("篩選特定產業", ["全部"] + sorted(list(df['industry'].dropna().unique())))
        
        st.sidebar.header("🧠 進階策略加選")
        enable_drawdown = st.sidebar.checkbox("開啟「回檔策略」", value=False)
        enable_strong = st.sidebar.checkbox("開啟「近期強勢群組」", value=False)
        
        if enable_drawdown:
            st.sidebar.markdown("---")
            st.sidebar.caption("🛠️ 回檔策略細項設定")
            support_mode = st.sidebar.selectbox("└ 籌碼支撐型態", ["全部符合", "單日爆發強勢型", "波段洗刷接貨型"])
            dynamic_threshold = st.sidebar.checkbox("└ 啟用股本規模動態門檻調整", value=True)
            min_dd = st.sidebar.slider("└ 最低回檔幅度(%)", 0, 50, 5)
            
        if enable_strong:
            st.sidebar.markdown("---")
            st.sidebar.caption("🛠️ 近期強勢群組細項設定")
            min_change = st.sidebar.slider("└ 最低今日漲幅(%)", -10, 10, 5)
        
        # 基礎過濾
        res = df[(df['price'] >= min_p) & (df['price'] <= max_p) & (df['vol'] >= min_v)].copy()
        if max_pe > 0:
            res = res[((res['pe'] > 0) & (res['pe'] <= max_pe)).fillna(False)]
            
        if target_industry != "全部":
            res = res
