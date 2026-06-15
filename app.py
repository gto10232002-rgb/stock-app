import streamlit as st
import pandas as pd
import requests
import datetime
import yfinance as yf

# ==========================================
# 1. 頁面配置與 CSS
# ==========================================
st.set_page_config(page_title="StockTool", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2.8rem !important; padding-bottom: 0rem !important; }
    h3 { margin-top: 0rem !important; margin-bottom: 0.4rem !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📊 台股多元策略選股系統")
st.caption("📌 關盤資訊會在每日 18:30 之後導入")

# ==========================================
# 2. 獲取台股基礎資料 (證交所 Open API)
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_base_data_v3():
    cols = ['code', 'name', 'price', 'vol', 'trade_value', 'pe', 'industry', 'chip_ratio', 'value_billion']
    empty_df = pd.DataFrame(columns=cols)

    df_price = pd.DataFrame()
    try:
        res_p = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", timeout=15)
        if res_p.status_code == 200 and res_p.json():
            raw = pd.DataFrame(res_p.json())
            df_price = raw[raw['Code'].str.len() == 4].copy()
            df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
            df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
            df_price['trade_value'] = pd.to_numeric(df_price['TradeValue'].str.replace(',', ''), errors='coerce')
            df_price = df_price[['Code', 'Name', 'price', 'vol', 'trade_value']].rename(columns={'Code': 'code', 'Name': 'name'})
    except Exception as e:
        st.sidebar.error(f"⚠️ 股價API異常: {e}")

    if df_price.empty:
        return empty_df

    df_pe = pd.DataFrame()
    try:
        res_pe = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", timeout=15)
        if res_pe.status_code == 200 and res_pe.json():
            raw_pe = pd.DataFrame(res_pe.json())
            df_pe = raw_pe[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
            df_pe['pe'] = pd.to_numeric(df_pe['pe'].str.replace(',', ''), errors='coerce')
    except Exception:
        pass

    df_ind = pd.DataFrame()
    try:
        res_ind = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", timeout=15)
        if res_ind.status_code == 200 and res_ind.json():
            raw_ind = pd.DataFrame(res_ind.json())
            df_ind = raw_ind[['公司代號', '產業別']].rename(columns={'公司代號': 'code', '產業別': 'industry'})
    except Exception:
        pass

    df_chips = pd.DataFrame()
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(7):
        d_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d_str}&selectType=ALLBUT0999&response=json"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and "data" in res.json():
                js = res.json()
                df_raw = pd.DataFrame(js["data"], columns=[c.strip() for c in js["fields"]])
                fi_c = [c for c in df_raw.columns if '外資' in c and '買賣超' in c][0]
                it_c = [c for c in df_raw.columns if '投信' in c and '買賣超' in c][0]
                
                df_chips['code'] = df_raw['證券代號'].astype(str).str.strip()
                df_chips['fi'] = pd.to_numeric(df_raw[fi_c].str.replace(',', ''), errors='coerce') / 1000
                df_chips['it'] = pd.to_numeric(df_raw[it_c].str.replace(',', ''), errors='coerce') / 1000
                break
        except Exception:
            continue

    df = pd.merge(df_price, df_chips, on='code', how='left') if not df_chips.empty else df_price.copy()
    for col in ['fi', 'it']:
        if col not in df.columns: df[col] = 0.0
    df['fi'] = df['fi'].fillna(0.0)
    df['it'] = df['it'].fillna(0.0)

    df = pd.merge(df, df_pe, on='code', how='left') if not df_pe.empty else df.assign(pe=pd.NA)
    df = pd.merge(df, df_ind, on='code', how='left') if not df_ind.empty else df.assign(industry='其他')
    
    ind_map = {
        "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維", "05": "電機機械",
        "06": "電器電纜", "07": "化學工業", "08": "生技醫療業", "09": "玻璃陶瓷", "10": "造紙工業",
        "11": "鋼鐵工業", "12": "橡膠工業", "13": "汽車工業", "14": "建材營建", "15": "航運業",
        "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨", "19": "綜合業", "20": "其他業",
        "24": "半導體業", "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業", 
        "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業"
    }
    df['industry'] = df['industry'].astype(str).str.strip().map(ind_map).fillna(df['industry'])
    df['industry'] = df['industry'].replace(['', 'nan', 'None', 'NaN'], '其他').fillna('其他')

    df['chip_ratio'] = 0.0
    v_mask = df['vol'] > 0
    df.loc[v_mask, 'chip_ratio'] = (((df.loc[v_mask, 'fi'] + df.loc[v_mask, 'it']) / df.loc[v_mask, 'vol']) * 100).round(2)
    df['chip_ratio'] = df['chip_ratio'].clip(upper=100.0).fillna(0.0)
    df['value_billion'] = (df['trade_value'] / 100000000).round(2).fillna(0.0)

    return df[cols]

# ==========================================
# ⚡ 批次獲取技術指標 (完美解決 Series / DataFrame 結構突變問題)
# ==========================================
def batch_append_tech_indicators(res_df):
    if res_df.empty:
        res_df['回檔%'] = pd.Series(dtype=float)
        res_df['今日漲幅%'] = pd.Series(dtype=float)
        return res_df

    codes = [f"{str(c).strip()}.TW" for c in res_df['code']]
    dd_map, chg_map = {}, {}
    
    try:
        data = yf.download(codes, period="1mo", progress=False)
        
        for c in res_df['code']:
            tk = f"{str(c).strip()}.TW"
            dd, chg = 0.0, 0.0
            closes, highs = None, None
            
            try:
                # 【防呆核心】動態判斷回傳的是 DataFrame 還是 Series
                if 'Close' in data:
                    if isinstance(data['Close'], pd.DataFrame):
                        if tk in data['Close'].columns:
                            closes = data['Close'][tk].dropna()
                            highs = data['High'][tk].dropna()
                    elif isinstance(data['Close'], pd.Series):
                        # 當 yfinance 自行降維成 Series 時的安全讀取
                        closes = data['Close'].dropna()
                        highs = data['High'].dropna()
            except Exception:
                pass
                
            if closes is not None and highs is not None and len(closes) >= 2:
                # 確保變數型態是標準的 float，避免計算出錯
                h_max = float(highs.max())
                cur = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                
                if h_max > 0: dd = round(((h_max - cur) / h_max) * 100, 2)
                if prev > 0: chg = round(((cur - prev) / prev) * 100, 2)
            
            dd_map[c] = float(dd)
            chg_map[c] = float(chg)
            
    except Exception:
        for c in res_df['code']:
            dd_map[c] = 0.0
            chg_map[c] = 0.0

    res_df['回檔%'] = res_df['code'].map(dd_map).fillna(0.0)
    res_df['今日漲幅%'] = res_df['code'].map(chg_map).fillna(0.0)
    return res_df

# ==========================================
# 3. 主程式邏輯
# ==========================================
try:
    with st.spinner("正在同步最新籌碼與產業數據..."):
        df = get_stock_base_data_v3()
    
    if df.empty:
        st.warning("📅 暫時無法從證交所取得完整即時資料。請確認網路連線或是否為非交易時間。")
    else:
        st.sidebar.header("🎯 基礎篩選條件")
        min_p = st.sidebar.number_input("最低股價", value=0.0)
        max_p = st.sidebar.number_input("最高股價", value=500.0)
        min_v = st.sidebar.number_input("最低成交量(張)", value=1000)
        max_pe = st.sidebar.number_input("最高本益比 (0為不限)", value=30.0)
        
        target_industry = st.sidebar.selectbox("篩選特定產業", ["全部"] + sorted(list(df['industry'].unique())))
        
        st.sidebar.header("🧠 進階策略加選")
        enable_drawdown = st.sidebar.checkbox("開啟「回檔策略」", value=False)
        enable_strong = st.sidebar.checkbox("開啟「近期強勢群組」", value=False)
        
        dynamic_threshold = False
        support_mode = "全部符合"
        min_dd = 0
        min_change = 0
        
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
        
        res = df[(df['price'] >= min_p) & (df['price'] <= max_p) & (df['vol'] >= min_v)].copy()
        if max_pe > 0:
            res = res[((res['pe'] > 0) & (res['pe'] <= max_pe)).fillna(False)]
        if target_industry != "全部":
            res = res[res['industry'] == target_industry]
            
        if not res.empty:
            with st.spinner(f"正在分析 {len(res)} 檔股票的即時技術指標..."):
                res = batch_append_tech_indicators(res)
        else:
            res['回檔%'] = pd.Series(dtype=float)
            res['今日漲幅%'] = pd.Series(dtype=float)

        if not res.empty:
            mask_drawdown = pd.Series(False, index=res.index)
            mask_strong = pd.Series(False, index=res.index)
            
            if enable_drawdown:
                sub_mask = pd.Series(True, index=res.index)
                if dynamic_threshold:
                    cond_large = (res['value_billion'] >= 5.0) & (res['chip_ratio'] >= 2.5)
                    cond_small = (res['value_billion'] < 5.0) & (res['chip_ratio'] >= 5.0)
                    sub_mask = sub_mask & (cond_large | cond_small)
                if support_mode == "單日爆發強勢型":
                    sub_mask = sub_mask & (res['chip_ratio'] >= 5.0)
                
                sub_mask = sub_mask & (res['回檔%'] >= min_dd)
                if support_mode == "波段洗刷接貨型":
                    sub_mask = sub_mask & (res['回檔%'] >= max(8.0, float(min_dd)))
                mask_drawdown = sub_mask
                
            if enable_strong:
                mask_strong = (res['今日漲幅%'] >= min_change)
            
            if enable_drawdown and enable_strong:
                res = res[mask_drawdown | mask_strong]
            elif enable_drawdown:
                res = res[mask_drawdown]
            elif enable_strong:
                res = res[mask_strong]

        res['支撐力道'] = "🔹 觀察中"
        if not res.empty:
            res.loc[res['chip_ratio'] >= 10.0, '支撐力道'] = "🔥 極強支撐"
            res.loc[(res['chip_ratio'] >= 5.0) & (res['chip_ratio'] < 10.0), '支撐力道'] = "✅ 健康買盤"
            
            if enable_strong and not enable_drawdown:
                res = res.sort_values(by='今日漲幅%', ascending=False)
            else:
                res = res.sort_values(by=['chip_ratio', '回檔%'], ascending=[False, False])

        res['K線連結'] = res['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
        
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
            if c in etf_db: return f"{n} ({','.join(etf_db[c])})"
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
        strategy_text = " 或 ".join(active_strategies) if active_strategies else "純基礎條件"
        
        is_advanced_strategy_active = enable_drawdown or enable_strong
        info_markdown = ""
        
        if not display_df.empty:
            total_count = len(display_df)
            current_df = display_df
            
            if is_advanced_strategy_active:
                ind_counts = display_df['產業'].value_counts()
                filtered_ind = [f"{ind}: {count} 檔" for ind, count in ind_counts.items() if count >= 3]
                
                if filtered_ind:
                    ind_lines = "\n".join([f"* {item}" for item in filtered_ind])
                    info_markdown = f"🎯 當前過濾組合：【{strategy_text}】\n\n**最終符合條件：{total_count} 檔**\n\n{ind_lines}"
                else:
                    info_markdown = f"🎯 當前過濾組合：【{strategy_text}】\n\n**最終符合條件：{total_count} 檔**\n\n* （目前沒有3檔以上共同產業的主力出現）"
            else:
                info_markdown = f"🎯 當前過濾組合：【{strategy_text}】\n\n**最終符合條件：{total_count} 檔**"
        else:
            current_df = pd.DataFrame(columns=['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結'])
            if is_advanced_strategy_active:
                info_markdown = f"🎯 當前過濾組合：【{strategy_text}】\n\n**最終符合條件：0 檔**\n\n* （目前沒有3檔以上共同產業的主力出現）"
            else:
                info_markdown = f"🎯 當前過濾組合：【{strategy_text}】\n\n**最終符合條件：0 檔**"

        st.info(info_markdown)
        
        st.dataframe(
            current_df[['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結']],
            column_config={
                "代號": st.column_config.TextColumn("代號", pinned=True, width="small"),  
                "名稱": st.column_config.TextColumn("名稱", pinned=True, width="medium"), 
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
    st.error(f"⚠️ 網頁系統執行異常: {e}")
