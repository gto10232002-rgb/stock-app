import streamlit as st
import pandas as pd
import requests
import datetime
import time
import yfinance as yf

# 頁面配置
st.set_page_config(page_title="StockTool", layout="wide")
st.markdown("### 📊 台股籌碼選股")

# 注入自訂 CSS，讓手機版的卡片排版更精美，並徹底消滅橫向滾動
st.markdown("""
<style>
    div[data-testid="stVerticalBlock"] > div:has(div.stock-card) {
        padding: 0px;
    }
    .stock-card {
        background-color: #f8f9fa;
        border-left: 5px solid #ff4b4b;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 12px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    html[data-theme="dark"] .stock-card {
        background-color: #1e222b;
        border-left: 5px solid #ff4b4b;
    }
    .stock-title {
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 6px;
    }
    .stock-metrics {
        display: flex;
        flex-wrap: wrap;
        gap: 12px;
        margin-bottom: 8px;
        font-size: 14px;
    }
    .metric-item {
        background: rgba(0,0,0,0.03);
        padding: 4px 8px;
        border-radius: 4px;
    }
    html[data-theme="dark"] .metric-item {
        background: rgba(255,255,255,0.05);
    }
    .stock-badge {
        font-weight: bold;
        font-size: 14px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# 快取功能 1：抓取證交所基本與籌碼資料 (每小時更新一次)
@st.cache_data(ttl=3600)
def get_stock_base_data():
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

    url_pe = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    res_pe = requests.get(url_pe, timeout=20)
    df_pe = pd.DataFrame()
    if res_pe.status_code == 200:
        raw_pe = pd.DataFrame(res_pe.json())
        df_pe = raw_pe[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
        df_pe['pe'] = pd.to_numeric(df_pe['pe'].str.replace(',', ''), errors='coerce')

    df_chips = pd.DataFrame()
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(7):
        date_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
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

    if df_price.empty or df_chips.empty:
        return pd.DataFrame()
        
    df = pd.merge(df_price, df_chips, on='code', how='inner')
    df = pd.merge(df, df_pe, on='code', how='left')
    df['chip_ratio'] = ((df['fi'] + df['it']) / df['vol'] * 100).round(2)
    df['value_billion'] = (df['trade_value'] / 100000000).round(2)
    return df

# 快取功能 2：獨立快取每檔股票的 yfinance 回檔率
@st.cache_data(ttl=3600)
def get_single_drawdown(code):
    try:
        hist = yf.Ticker(f"{code}.TW").history(period="1mo")
        if not hist.empty:
            high_1m = hist['High'].max()
            current = hist['Close'].iloc[-1]
            if high_1m > 0:
                return round(((high_1m - current) / high_1m) * 100, 2)
    except:
        pass
    return 0.0

# --- 主程式區塊 ---
try:
    with st.spinner("正在同步最新籌碼數據..."):
        df = get_stock_base_data()
    
    if df.empty:
        st.warning("暫時無法取得證交所資料，請確認開盤日或稍後再試。")
    else:
        # 側邊欄：基礎篩選
        st.sidebar.header("🎯 基礎篩選條件")
        min_p = st.sidebar.number_input("最低股價", value=0.0)
        max_p = st.sidebar.number_input("最高股價", value=500.0)
        min_v = st.sidebar.number_input("最低成交量(張)", value=1000)
        max_pe = st.sidebar.number_input("最高本益比 (0為不限)", value=30.0)
        
        # 進階篩選設定
        st.sidebar.header("🛡️ 進階篩選設定")
        apply_lei_rules = st.sidebar.checkbox("是否套用雷老闆實務心法篩選", value=True)
        
        if apply_lei_rules:
            support_mode = st.sidebar.selectbox(
                "└ 籌碼支撐型態",
                ["全部符合", "單日爆發強勢型 (集中度>5%)", "波段洗刷接貨型 (高回檔+法人守穩)"]
            )
            dynamic_threshold = st.sidebar.checkbox(
                "└ 啟用股本規模動態門檻調整", 
                value=True,
                help="大型股門檻自動調降至2.5%；中小型股維持5.0%"
            )
            min_dd = st.sidebar.slider("└ 最低回檔幅度(%)", 0, 50, 5)
        
        # --- 第一階段：基礎與基本面篩選 ---
        res = df[(df['price'] >= min_p) & (df['price'] <= max_p) & (df['vol'] >= min_v)].copy()
        if max_pe > 0:
            res = res[(res['pe'] > 0) & (res['pe'] <= max_pe)]
            
        # --- 第二階段：根據總開關決定是否套用籌碼與回檔心法 ---
        if apply_lei_rules:
            if dynamic_threshold:
                cond_large = (res['value_billion'] >= 5.0) & (res['chip_ratio'] >= 2.5)
                cond_small = (res['value_billion'] < 5.0) & (res['chip_ratio'] >= 5.0)
                res = res[cond_large | cond_small]
                
            if support_mode == "單日爆發強勢型 (集中度>5%)":
                res = res[res['chip_ratio'] >= 5.0]
                
            if not res.empty:
                with st.spinner(f"正在分析 {len(res)} 檔目標個股的歷史回檔波動..."):
                    res['回檔%'] = res['code'].apply(get_single_drawdown)
                
                res = res[res['回檔%'] >= min_dd]
                
                if support_mode == "波段洗刷接貨型 (高回檔+法人守穩)":
                    res = res[res['回檔%'] >= max(8.0, min_dd)]
            else:
                res['回檔%'] = pd.Series(dtype=float)

            def judge_support_strength(row):
                if row['chip_ratio'] >= 10.0:
                    return "🔥 極強支撐 (籌碼單日大爆發)"
                elif row['chip_ratio'] >= 5.0:
                    return "✅ 健康買盤 (強勢守穩股)"
                elif row['value_billion'] >= 5.0 and row['chip_ratio'] >= 2.5:
                    return "🏛️ 大型股法人出資撐盤"
                else:
                    return "🔹 籌碼中性/觀察中"

            if not res.empty:
                res['支撐力道'] = res.apply(judge_support_strength, axis=1)
                res = res.sort_values(by=['chip_ratio', '回檔%'], ascending=[False, False])
            else:
                res['支撐力道'] = pd.Series(dtype=str)
                
        else:
            res['回檔%'] = 0.0
            res['支撐力道'] = "未啟用心法篩選"
            if not res.empty:
                res = res.sort_values(by='chip_ratio', ascending=False)

        # 輸出統計結果
        st.success(f"🎯 篩選完畢，最終符合條件：{len(res)} 檔")
        
        # --- 【高規格手機排版優化】改用直覺下滑卡片流 ---
        if res.empty:
            st.info("無符合當前條件的股票，請調整左側篩選標準。")
        else:
            for idx, row in res.iterrows():
                # 建立一個獨立精美的 HTML 卡片，把支撐力道、回檔、成交額全部清晰展現
                card_html = f"""
                <div class="stock-card">
                    <div class="stock-title">📈 {row['code']} {row['name']}</div>
                    <div class="stock-badge">📊 進場參考：{row['支撐力道']}</div>
                    <div class="stock-metrics">
                        <div class="metric-item">💰 股價: <b>{row['price']:.2f}元</b></div>
                        <div class="metric-item">📉 回檔幅度: <b>{row['回檔%']:.1f}%</b></div>
                        <div class="metric-item">🎯 籌碼集中度: <b>{row['chip_ratio']:.2f}%</b></div>
                        <div class="metric-item">💎 成交額: <b>{row['value_billion']:.1f}億</b></div>
                        <div class="metric-item">⏳ PE: <b>{row['pe'] if pd.notna(row['pe']) else '--'}</b></div>
                    </div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                
                # 在卡片下方緊接著放一塊超好按的大按鈕，點擊直接看 Yahoo K 線
                yahoo_url = f"https://tw.stock.yahoo.com/quote/{row['code']}"
                st.link_button(f"查看 {row['name']} 詳細 K 線圖", url=yahoo_url, use_container_width=True)
                st.markdown("---") # 分隔線

except Exception as e:
    st.error(f"程式發生錯誤: {e}")
