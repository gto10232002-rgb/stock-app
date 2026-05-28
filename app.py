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
    # A. 取得每日收盤行情
    url_price = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res_price = requests.get(url_price, timeout=20)
    df_price = pd.DataFrame()
    if res_price.status_code == 200:
        raw_price = pd.DataFrame(res_price.json())
        df_price = raw_price[raw_price['Code'].str.len() == 4].copy()
        df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
        df_price['trade_value'] = pd.to_numeric(raw_price['TradeValue'].str.replace(',', ''), errors='coerce')
        df_price = df_price[['Code', 'Name', 'price', 'vol', 'trade_value']].rename(columns={'Code': 'code', 'Name': 'name'})

    # B. 取得本益比資料
    url_pe = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    res_pe = requests.get(url_pe, timeout=20)
    df_pe = pd.DataFrame()
    if res_pe.status_code == 200:
        raw_pe = pd.DataFrame(res_pe.json())
        df_pe = raw_pe[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
        df_pe['pe'] = pd.to_numeric(df_pe['pe'].str.replace(',', ''), errors='coerce')

    # C. 取得產業別對照
    url_industry = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    res_ind = requests.get(url_industry, timeout=20)
    df_ind = pd.DataFrame()
    if res_ind.status_code == 200:
        raw_ind = pd.DataFrame(res_ind.json())
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

    # D. 🛡️ 終極安全晶片籌碼撈取機制 (防止 IndexError)
    df_chips = pd.DataFrame()
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(7):
        date_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
        try:
            res = requests.get(url, headers=headers, timeout=20)
            if res.status_code == 200 and "data" in res.json():
                data = res.json()["data"]
                fields = res.json()["fields"]
                df_raw = pd.DataFrame(data, columns=fields)
                df_raw.columns = df_raw.columns.str.strip()
                
                # 安全模糊搜尋欄位，不使用固定強取以免結構改變
                fi_cols = [c for c in df_raw.columns if '外資' in c and '買賣超' in c]
                it_cols = [c for c in df_raw.columns if '投信' in c and '買賣超' in c]
                
                if fi_cols and it_cols and '證券代號' in df_raw.columns:
                    fi_col = fi_cols[0]
                    it_col = it_cols[0]
                    df_chips['code'] = df_raw['證券代號'].astype(str).str.strip()
                    df_chips['fi'] = pd.to_numeric(df_raw[fi_col].str.replace(',', ''), errors='coerce') / 1000
                    df_chips['it'] = pd.to_numeric(df_raw[it_col].str.replace(',', ''), errors='coerce') / 1000
                    break  # 成功撈到一筆完整的就收工
        except Exception:
            pass  # 如果這天出錯就順延到前一天
        time.sleep(0.3)

    if df_price.empty or df_chips.empty:
        return pd.DataFrame()
        
    df = pd.merge(df_price, df_chips, on='code', how='inner')
    df = pd.merge(df, df_pe, on='code', how='left')
    df = pd.merge(df, df_ind, on='code', how='left')
    df['industry'] = df['industry'].fillna('其他')
    df['chip_ratio'] = ((df['fi'] + df['it']) / df['vol'] * 100).round(2)
    df['value_billion'] = (df['trade_value'] / 100000000).round(2)
    return df

try:
    with st.spinner("正在同步最新籌碼與產業數據..."):
        df = get_stock_base_data()
    
    if df.empty:
        st.warning("暫時無法從證交所取得完整資料，請檢查網路連線或非交易日限制。")
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
        
        # 1. 執行基礎過濾
        res = df[(df['price'] >= min_p) & (df['price'] <= max_p) & (df['vol'] >= min_v)].copy()
        if max_pe > 0:
            res = res[(res['pe'] > 0) & (res['pe'] <= max_pe)]
            
        if target_industry != "全部":
            res = res[res['industry'] == target_industry]
            
        # 🛡️ 核心安全防護欄位初始化
        res['回檔%'] = 0.0
        res['今日漲幅%'] = 0.0
        res['支撐力道'] = "🔹 觀察中"
        res['K線連結'] = ""
        
        dd_dict = {}
        chg_dict = {}
        
        # 2. ⚡ 矩陣運算核心（全面升級為 Layout-Independent 智能元組掃描器） ⚡
        if not res.empty and (enable_drawdown or enable_strong):
            with st.spinner(f"正在以矩陣加速模式分析 {len(res)} 檔股票的即時技術指標..."):
                valid_codes = res['code'].astype(str).str.strip().tolist()
                ticker_list = [f"{c}.TW" for c in valid_codes]
                
                try:
                    hist_data = yf.download(ticker_list, period="1mo", threads=True, progress=False)
                    
                    if not hist_data.empty:
                        close_df = pd.DataFrame(index=hist_data.index, columns=valid_codes, dtype=float)
                        high_df = pd.DataFrame(index=hist_data.index, columns=valid_codes, dtype=float)
                        
                        # A. 針對 MultiIndex 多證券傳回結構的終極動態掃描器
                        if isinstance(hist_data.columns, pd.MultiIndex):
                            for col in hist_data.columns:
                                metric = next((str(item).strip() for item in col if str(item).strip() in ['Close', 'High']), None)
                                code = next((str(item).replace('.TW', '').strip() for item in col if str(item).replace('.TW', '').strip() in valid_codes), None)
                                
                                if metric == 'Close' and code:
                                    close_df[code] = hist_data[col]
                                elif metric == 'High' and code:
                                    high_df[code] = hist_data[col]
                                        
                        # B. 針對單一證券降維後的常規單層 Index 結構
                        else:
                            if 'Close' in hist_data.columns and 'High' in hist_data.columns:
                                single_code = valid_codes[0]
                                close_df[single_code] = hist_data['Close']
                                high_df[single_code] = hist_data['High']
                        
                        # 剔除尾部尚未開盤的完全空值列
                        while len(close_df) > 0 and close_df.iloc[-1].isna().all():
                            close_df = close_df.iloc[:-1]
                            high_df = high_df.iloc[:-1]
                            
                        if len(close_df) >= 2:
                            close_df = close_df.ffill()
                            high_df = high_df.ffill()
                            
                            max_high = high_df.max()
                            last_close = close_df.iloc[-1]
                            prev_close = close_df.iloc[-2]
                            
                            drawdown_series = ((max_high - last_close) / max_high * 100).round(2)
                            change_series = ((last_close - prev_close) / prev_close * 100).round(2)
                            
                            dd_dict = drawdown_series.to_dict()
                            chg_dict = change_series.to_dict()
                            
                            res['回檔%'] = res['code'].astype(str).str.strip().map(dd_dict).fillna(0.0)
                            res['今日漲幅%'] = res['code'].astype(str).str.strip().map(chg_dict).fillna(0.0)
                                
                except Exception as e:
                    st.sidebar.warning(f"技術指標載入提示: {e}")

        # 3. 策略過濾門檻
        if not res.empty and (enable_drawdown or enable_strong):
            if enable_drawdown:
                if dynamic_threshold:
                    cond_large = (res['value_billion'] >= 5.0) & (res['chip_ratio'] >= 2.5)
                    cond_small = (res['value_billion'] < 5.0) & (res['chip_ratio'] >= 5.0)
                    res = res[(cond_large | cond_small).fillna(False)]
                if support_mode == "單日爆發強勢型":
                    res = res[(res['chip_ratio'] >= 5.0).fillna(False)]
                res = res[(res['回檔%'] >= min_dd).fillna(False)]
                if support_mode == "波段洗刷接貨型":
                    res = res[(res['回檔%'] >= max(8.0, float(min_dd))).fillna(False)]
                    
            if enable_strong:
                res = res[(res['今日漲幅%'] >= min_change).fillna(False)]

        # 4. 排序與計算力道標籤
        def judge_support_strength(row):
            if row['chip_ratio'] >= 10.0: return "🔥 極強支撐"
            elif row['chip_ratio'] >= 5.0: return "✅ 健康買盤"
            else: return "🔹 觀察中"
            
        if not res.empty:
            res['支撐力道'] = res.apply(judge_support_strength, axis=1)
            if enable_strong:
                res = res.sort_values(by='今日漲幅%', ascending=False)
            else:
                res = res.sort_values(by=['chip_ratio', '回檔%'], ascending=[False, False])

        res['K線連結'] = res['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
        
        # 5. 🏷️ 熱門 ETF 成分股標籤資料庫
        etf_db = {
            "2330": ["0050", "00919", "00929"], "2317": ["0050", "00919", "00929"], 
            "2454": ["0050", "0056", "00878", "00919", "00929", "00940"], "2308": ["0050", "00929"], 
            "3711": ["0050", "0056", "00878", "00919"], "2303": ["0050", "0056", "00878", "00919", "00929", "00940"],
            "2881": ["0050", "00878", "00919", "00940"], "2882": ["0050", "00878", "00919"], 
            "2891": ["0050", "0056", "00878", "00919", "00940"], "2382": ["0050", "0056", "00878", "00919", "00940"], 
            "2886":
