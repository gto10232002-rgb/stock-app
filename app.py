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

    url_industry = "https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
    res_ind = requests.get(url_industry, timeout=20)
    df_ind = pd.DataFrame()
    if res_ind.status_code == 200:
        raw_ind = pd.DataFrame(res_ind.json())
        df_ind = raw_ind[['公司代號', '產業別']].rename(columns={'公司代號': 'code', '產業別': 'industry'})

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
    df = pd.merge(df, df_ind, on='code', how='left')
    df['industry'] = df['industry'].fillna('其他')
    df['chip_ratio'] = ((df['fi'] + df['it']) / df['vol'] * 100).round(2)
    df['value_billion'] = (df['trade_value'] / 100000000).round(2)
    return df

@st.cache_data(ttl=3600)
def get_technical_data(code):
    try:
        hist = yf.Ticker(f"{code}.TW").history(period="1mo")
        if not hist.empty and len(hist) >= 2:
            high_1m = hist['High'].max()
            current = hist['Close'].iloc[-1]
            prev_close = hist['Close'].iloc[-2]
            
            drawdown = round(((high_1m - current) / high_1m) * 100, 2) if high_1m > 0 else 0.0
            change_pct = round(((current - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0
                
            return {'回檔%': drawdown, '今日漲幅%': change_pct}
    except:
        pass
    return {'回檔%': 0.0, '今日漲幅%': 0.0}

try:
    with st.spinner("正在同步最新籌碼與產業數據..."):
        df = get_stock_base_data()
    
    if df.empty:
        st.warning("暫時無法取得證交所資料，請確認開盤日或稍後再試。")
    else:
        # --- 側邊欄改版 ---
        st.sidebar.header("🎯 基礎篩選條件")
        min_p = st.sidebar.number_input("最低股價", value=0.0)
        max_p = st.sidebar.number_input("最高股價", value=500.0)
        min_v = st.sidebar.number_input("最低成交量(張)", value=1000)
        max_pe = st.sidebar.number_input("最高本益比 (0為不限)", value=30.0)
        
        target_industry = st.sidebar.selectbox("篩選特定產業", ["全部"] + sorted(list(df['industry'].dropna().unique())))
        
        # 🎯 策略大分流
        st.sidebar.header("🧠 策略核心選擇")
        strategy = st.sidebar.selectbox(
            "選擇選股策略",
            ["純基礎條件", "雷老闆回檔心法", "影片強勢族群群聚"]
        )
        
        # 根據不同策略顯示不同參數
        min_dd = 0.0
        min_change = -99.0
        
        if strategy == "雷老闆回檔心法":
            support_mode = st.sidebar.selectbox("└ 籌碼支撐型態", ["全部符合", "單日爆發強勢型", "波段洗刷接貨型"])
            dynamic_threshold = st.sidebar.checkbox("└ 啟用股本規模動態門檻調整", value=True)
            min_dd = st.sidebar.slider("└ 最低回檔幅度(%)", 0, 50, 5)
        elif strategy == "影片強勢族群群聚":
            min_change = st.sidebar.slider("└ 最低今日漲幅(%) [建議 5% 以上]", -10, 10, 5)
        
        # 執行基礎過濾
        res = df[(df['price'] >= min_p) & (df['price'] <= max_p) & (df['vol'] >= min_v)].copy()
        if max_pe > 0:
            res = res[(res['pe'] > 0) & (res['pe'] <= max_pe)]
            
        if target_industry != "全部":
            res = res[res['industry'] == target_industry]
            
        # 執行策略過濾
        if not res.empty:
            with st.spinner(f"正在透過 Yahoo Finance 計算 {len(res)} 檔股票的即時技術指標..."):
                tech_data = res['code'].apply(get_technical_data).apply(pd.Series)
                res = pd.concat([res, tech_data], axis=1)
            
            # 分流過濾邏輯
            if strategy == "雷老闆回檔心法":
                if dynamic_threshold:
                    cond_large = (res['value_billion'] >= 5.0) & (res['chip_ratio'] >= 2.5)
                    cond_small = (res['value_billion'] < 5.0) & (res['chip_ratio'] >= 5.0)
                    res = res[cond_large | cond_small]
                if support_mode == "單日爆發強勢型":
                    res = res[res['chip_ratio'] >= 5.0]
                res = res[res['回檔%'] >= min_dd]
                if support_mode == "波段洗刷接貨型":
                    res = res[res['回檔%'] >= max(8.0, min_dd)]
                    
            elif strategy == "影片強勢族群群聚":
                res = res[res['今日漲幅%'] >= min_change]
        else:
            res['回檔%'] = pd.Series(dtype=float)
            res['今日漲幅%'] = pd.Series(dtype=float)

        # 支撐力道標籤
        def judge_support_strength(row):
            if row['chip_ratio'] >= 10.0: return "🔥 極強支撐"
            elif row['chip_ratio'] >= 5.0: return "✅ 健康買盤"
            else: return "🔹 觀察中"
            
        if not res.empty:
            res['支撐力道'] = res.apply(judge_support_strength, axis=1)
            # 排序邏輯分流：強勢策略優先排漲幅，回檔策略優先排集中度
            if strategy == "影片強勢族群群聚":
                res = res.sort_values(by='今日漲幅%', ascending=False)
            else:
                res = res.sort_values(by=['chip_ratio', '回檔%'], ascending=[False, False])
        else:
            res['支撐力道'] = pd.Series(dtype=str)

        res['K線連結'] = res['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
        
        display_df = res.rename(columns={
            'code': '代號', 'name': '名稱', 'industry': '產業', 'price': '股價', 
            'chip_ratio': '集中度%', 'pe': '本益比', 'value_billion': '成交額(億)'
        })
        
        st.success(f"🎯 策略：【{strategy}】｜ 最終符合條件：{len(display_df)} 檔")
        
        # 族群共振看板 (獨立觸發)
        if not display_df.empty and '今日漲幅%' in display_df.columns:
            strong_stocks = display_df[display_df['今日漲幅%'] >= 5.0]
            if not strong_stocks.empty:
                industry_counts = strong_stocks['產業'].value_counts()
                hot_industries = industry_counts[industry_counts >= 2]
                
                if not hot_industries.empty:
                    st.info("🚨 **發現族群共振！以下產業出現多檔大漲股：**")
                    cols = st.columns(min(len(hot_industries), 5))
                    for i, (ind, count) in enumerate(hot_industries.items()):
                        if i < 5:
                            with cols[i]:
                                st.metric(label=f"🔥 {ind}", value=f"{count} 檔強勢")

        st.dataframe(
            display_df[['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結']],
            column_config={
                "今日漲幅%": st.column_config.NumberColumn(format="%.2f %%"),
                "股價": st.column_config.NumberColumn(format="%.2f"),
                "回檔%": st.column_config.NumberColumn(format="%.2f %%"),
                "集中度%": st.column_config.NumberColumn(format="%.2f %%"),
                "成交額(億)": st.column_config.NumberColumn(format="%.2f 億"),
                "本益比": st.column_config.NumberColumn(format="%.2f"),
                "K線連結": st.column_config.LinkColumn("K線", display_text="📈查看")
            },
            use_container_width=True,
            hide_index=True,
            height=650
        )

except Exception as e:
    st.error(f"程式發生錯誤: {e}")
