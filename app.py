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
        
        ind_map = {
            "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
            "05": "電機機械", "06": "電器電纜", "07": "化學工業", "08": "生技醫療業",
            "09": "玻璃陶瓷", "10": "造紙工業", "11": "鋼鐵工業", "12": "橡膠工業",
            "13": "汽車工業", "14": "建材營建", "15": "航運業", "16": "觀光餐旅",
            "17": "金融保險", "18": "貿易百貨", "19": "綜合業", "20": "其他業",
            "23": "油電燃氣業", "24": "半導體業", "25": "電腦及週邊設備業", 
            "26": "光電業", "27": "通信網路業", "28": "電子零組件業", 
            "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業",
            "35": "綠能環保", "36": "數位雲端", "37": "運動休閒", "38": "居家生活"
        }
        df_ind['industry'] = df_ind['industry'].astype(str).str.strip().map(ind_map).fillna(df_ind['industry'])

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

try:
    with st.spinner("正在同步最新籌碼與產業數據..."):
        df = get_stock_base_data()
    
    if df.empty:
        st.warning("暫時無法取得證交所資料，請確認開盤日或稍後再試。")
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
            
        # 2. ⚡ 完全向量化高速批次下載與運算模式 (大幅提高搜尋速度) ⚡
        if not res.empty:
            if enable_drawdown or enable_strong:
                with st.spinner(f"正在以矩陣加速模式分析 {len(res)} 檔股票的即時技術指標..."):
                    ticker_list = [f"{str(c).strip()}.TW" for c in res['code']]
                    try:
                        hist_data = yf.download(ticker_list, period="1mo", progress=False)
                        
                        dd_dict = {}
                        chg_dict = {}
                        
                        # 判定 yfinance 回傳的多股 MultiIndex 結構
                        if isinstance(hist_data.columns, pd.MultiIndex):
                            if 'High' in hist_data.columns.levels[0] and 'Close' in hist_data.columns.levels[0]:
                                max_highs = hist_data['High'].max()
                                last_closes = hist_data['Close'].iloc[-1] if len(hist_data) >= 1 else pd.Series(dtype=float)
                                prev_closes = hist_data['Close'].iloc[-2] if len(hist_data) >= 2 else pd.Series(dtype=float)
                                
                                # 使用高速記憶體映射，完全取代緩慢的 pandas 切片迴圈
                                for tk in max_highs.index:
                                    code_clean = tk.split('.')[0]
                                    h = max_highs[tk]
                                    c = last_closes.get(tk, 0.0)
                                    p = prev_closes.get(tk, 0.0)
                                    
                                    dd_dict[code_clean] = round(((h - c) / h) * 100, 2) if h > 0 else 0.0
                                    chg_dict[code_clean] = round(((c - p) / p) * 100, 2) if p > 0 else 0.0
                        else:
                            # 單一檔股票回傳時的扁平結構處理
                            if 'High' in hist_data.columns and 'Close' in hist_data.columns:
                                max_high = hist_data['High'].max()
                                last_close = hist_data['Close'].iloc[-1] if len(hist_data) >= 1 else 0.0
                                prev_close = hist_data['Close'].iloc[-2] if len(hist_data) >= 2 else 0.0
                                
                                code_clean = str(res['code'].iloc[0]).strip()
                                dd_dict[code_clean] = round(((max_high - last_close) / max_high) * 100, 2) if max_high > 0 else 0.0
                                chg_dict[code_clean] = round(((last_close - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0
                                
                        res['回檔%'] = res['code'].map(dd_dict).fillna(0.0)
                        res['今日漲幅%'] = res['code'].map(chg_dict).fillna(0.0)
                    except Exception as e:
                        st.error(f"Yahoo Finance 批次連線異常: {e}")
                        res['回檔%'] = 0.0
                        res['今日漲幅%'] = 0.0
            else:
                res['回檔%'] = 0.0
                res['今日漲幅%'] = 0.0
        else:
            res['回檔%'] = pd.Series(dtype=float)
            res['今日漲幅%'] = pd.Series(dtype=float)

        # 3. 篩選策略過濾
        if not res.empty and (enable_drawdown or enable_strong):
            if enable_drawdown:
                if dynamic_threshold:
                    cond_large = (res['value_billion'] >= 5.0) & (res['chip_ratio'] >= 2.5)
                    cond_small = (res['value_billion'] < 5.0) & (res['chip_ratio'] >= 5.0)
                    res = res[cond_large | cond_small]
                if support_mode == "單日爆發強勢型":
                    res = res[res['chip_ratio'] >= 5.0]
                res = res[res['回檔%'] >= min_dd]
                if support_mode == "波段洗刷接貨型":
                    res = res[res['回檔%'] >= max(8.0, min_dd)]
                    
            if enable_strong:
                res = res[res['今日漲幅%'] >= min_change]

        # 4. 計算支撐力道標籤與排序
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
        else:
            res['支撐力道'] = pd.Series(dtype=str)

        res['K線連結'] = res['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
        
        # 5. 🏷️ 建立熱門 ETF 成分股對照表並整合至名稱欄位
        etf_db = {
            "2330": ["0050", "00919", "00929"], "2317": ["0050", "00919", "00929"], 
            "2454": ["0050", "0056", "00878", "00919", "00929", "00940"], "2308": ["0050", "00929"], 
            "3711": ["0050", "0056", "00878", "00919"], "2303": ["0050", "0056", "00878", "00919", "00929", "00940"],
            "2881": ["0050", "00878", "00919", "00940"], "2882": ["0050", "00878", "00919"], 
            "2891": ["0050", "0056", "00878", "00919", "00940"], "2382": ["0050", "0056", "00878", "00919", "00940"], 
            "2886": ["0050", "00878"], "3008": ["0050", "00919", "00929"], "2884": ["0050"], 
            "2885": ["0050", "00878", "00940"], "2892": ["0050", "00940"], 
            "2357": ["0050", "0056", "00878", "00919", "00929", "00940"], "3231": ["0050", "0056", "00878", "00929"], 
            "1216": ["0050", "0056", "00878", "00940"], "2412": ["0050", "00878"], "1301": ["0050"], 
            "1303": ["0050"], "2603": ["0050", "0056", "00878", "00919", "00940"], "3037": ["0050"],
            "2301": ["0050", "0056", "00878", "00929"], "4904": ["0050", "00878"], "2327": ["0050", "00919"], 
            "3045": ["0050", "00878", "00940"], "2408": ["0050"], "2449": ["0050", "0056", "00878"], 
            "2345": ["0050"], "2395": ["0050"], "2360": ["0050"], "2368": ["0050"], "3017": ["0050"], 
            "2383": ["0050"], "2207": ["0050"], "6669": ["0050"], "3653": ["0050"], "3661": ["0050"], 
            "2002": ["0050"], "5880": ["0050"], "2880": ["0050", "0056", "00878"], "2883": ["0050", "00940"],
            "2890": ["0050", "00940"], "6505": ["0050"], "6919": ["0050"], "7769": ["0050"], 
            "2059": ["0050"], "2344": ["0050"], "2376": ["0056", "00878"], 
            "2324": ["0056", "00878", "00919", "00929", "00940"], 
            "2356": ["0056", "00878", "00940"], "2385": ["0056", "00940"], 
            "3034": ["0056", "00878", "00919", "00929", "00940"], "3702": ["0056", "00940"],
            "4938": ["0056", "00929", "00940"], "3293": ["0056", "00878", "00940"], 
            "2474": ["0056", "00878", "00940"], "3005": ["0056", "00940"], "2379": ["0056", "00878", "00940"], 
            "2404": ["0056", "00919", "00929", "00940"], "6121": ["0056"], 
            "2618": ["0056", "00878", "00919", "00940"], "5347": ["0056", "00878", "00919"],
            "3044": ["0056", "00929", "00940"], "2610": ["0056", "00940"], "3036": ["0056", "00929", "00940"],
            "1504": ["0056", "00940"], "2312": ["0056", "00940"], "2458": ["0056", "00940"], 
            "3042": ["0056", "00940"], "5469": ["0056", "00940"], "6278": ["0056", "00940"], 
            "2915": ["0056", "00940"], "8069": ["0056", "00940"], "3023": ["0056", "00940"], 
            "2421": ["0056", "00940"], "6414": ["0056", "00940"], "3406": ["0056", "00919", "00940"],
            "2439": ["0056", "00940"], "6188": ["0056", "00940"], "6285": ["0056", "00940"], 
            "8016": ["0056", "00940"], "6139": ["0056", "00940"], "5269": ["0056", "00940"], 
            "6196": ["0056", "00940"], "6239": ["0056", "00919", "00929", "00940"], "4958": ["00878", "00919"], 
            "1402": ["00878"], "2912": ["00878", "00940"], "2609": ["00919"], "8209": ["00919"],
            "6488": ["00929", "00940"], "2801": ["00940"], "9904": ["00940"], "1102": ["00940"], 
            "4915": ["00940"], "2615": ["00940"], "1319": ["00940"], "3706": ["00940"], 
            "6176": ["00940"], "1513": ["00940"], "2393": ["00940"], "6257": ["00940"]
        }

        def merge_etf_info(row):
            c = str(row['code']).strip()
            n = str(row['name']).strip()
            if c in etf_db:
                return f"{n} ({','.join(etf_db[c])})"
            return n

        if not res.empty:
            res['name'] = res.apply(merge_etf_info, axis=1)

        display_df = res.rename(columns={
            'code': '代號', 'name': '名稱', 'industry': '產業', 'price': '股價', 
            'chip_ratio': '集中度%', 'pe': '本益比', 'value_billion': '成交額(億)'
        })
        
        active_strategies = []
        if enable_drawdown: active_strategies.append("回檔策略")
        if enable_strong: active_strategies.append("近期強勢群組")
        strategy_text = " + ".join(active_strategies) if active_strategies else "純基礎條件"
        
        st.success(f"🎯 當前過濾組合：【{strategy_text}】｜ 最終符合條件：{len(display_df)} 檔")
        
        # 族群共振看板
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
