import streamlit as st
import pandas as pd
import requests
import datetime
import time
import yfinance as yf

# 頁面配置
st.set_page_config(page_title="StockTool", layout="wide")

# 🎯 【修改點 1】注入 CSS：消滅頂部無效空白、縮緊標題間距
st.markdown("""
<style>
    /* 縮小整頁頂部與底部的邊距 */
    .block-container {
        padding-top: 1.2rem !important;
        padding-bottom: 0rem !important;
    }
    /* 讓主標題緊貼頂部 */
    h3 {
        margin-top: 0rem !important;
        margin-bottom: 0.4rem !important;
    }
</style>
""", unsafe_allow_html=True)

# 保持乾淨主標
st.markdown("### 📊 台股籌碼選股")

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
                help="大型股(成交額>5億)門檻自動調降至2.5%；中小型股維持5.0%"
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
                    return "🔥 極強支撐 (單日爆發)"
                elif row['chip_ratio'] >= 5.0:
                    return "✅ 健康買盤 (強勢股)"
                elif row['value_billion'] >= 5.0 and row['chip_ratio'] >= 2.5:
                    return "🏛️ 大型股法人撐盤"
                else:
                    return "🔹 弱支撐/觀察中"

            if not res.empty:
                res['支撐力道'] = res.apply(judge_support_strength, axis=1)
                res = res.sort_values(by=['chip_ratio', '回檔%'], ascending=[False, False])
            else:
                res['支撐力道'] = pd.Series(dtype=str)
                
        else:
            res['回檔%'] = 0.0
            res['支撐力道'] = "未啟用心法"
            if not res.empty:
                res = res.sort_values(by='chip_ratio', ascending=False)

        # 建立 Yahoo K線連結
        res['K線連結'] = res['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
        
        display_df = res.rename(columns={
            'code': '代號', 
            'name': '名稱', 
            'price': '股價', 
            'chip_ratio': '集中度%', 
            'pe': '本益比',
            'value_billion': '成交額(億)'
        })
        
        st.success(f"🎯 篩選完畢，最終符合條件：{len(display_df)} 檔")
        
        # 🎯 【修改點 2】在大表格最下方新增 height=650，強迫表格向下伸展、吃掉空白
        st.dataframe(
            display_df[['代號', '名稱', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結']],
            column_config={
                "股價": st.column_config.NumberColumn(format="%.2f"),
                "回檔%": st.column_config.NumberColumn(format="%.2f %%"),
                "集中度%": st.column_config.NumberColumn(format="%.2f %%"),
                "成交額(億)": st.column_config.NumberColumn(format="%.2f 億"),
                "本益比": st.column_config.NumberColumn(format="%.2f"),
                "K線連結": st.column_config.LinkColumn("K線", display_text="📈查看")
            },
            use_container_width=True,
            hide_index=True,
            height=650  # <-- 加上這一行，中間資料區立刻放大！
        )

except Exception as e:
    st.error(f"程式發生錯誤: {e}")
