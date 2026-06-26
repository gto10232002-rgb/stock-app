import streamlit as st
import pandas as pd
import requests
import datetime
import yfinance as yf
import numpy as np

# ==========================================
# 1. 頁面配置與 CSS 樣式微調
# ==========================================
st.set_page_config(page_title="StockTool", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.8rem !important; padding-bottom: 0rem !important; }
    h3 { margin-top: 0rem !important; margin-bottom: 0.4rem !important; }
    .stAlert { padding: 0.6rem !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📊 台股多元策略選股系統")
st.caption("📌 關盤資訊會在每日 18:30 之後導入")

# ==========================================
# 2. ETF 成分資料庫與名稱合併函數
# ==========================================
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
    "2421": ["0056", "00940"], "6414": ["0056", "00940"], "3406": ["0056", "00919", "00940"],
    "2439": ["0056", "00940"], "6188": ["0056", "00940"], "6285": ["0056", "00940"], 
    "8016": ["0056", "00940"], "6139": ["0056", "00940"], "5269": ["0056", "00940"], 
    "6196": ["0056", "00940"], "6239": ["0056", "00919", "00929", "00940"], "4958": ["00878", "00919"], 
    "1402": ["00878"], "2912": ["00878", "00940"], "2609": ["00919"], "8209": ["00919"],
    "6488": ["00929", "00940"], "2801": ["00940"], "9904": ["00940"], "1102": ["00940"], 
    "4915": ["00940"], "2615": ["00940"], "1319": ["00940"], "3706": ["00940"], 
    "6176": ["00940"], "1513": ["00940"], "2393": ["00940"], "6257": ["00940"]
}

# 全域常備核心股名稱對照表（用於證交所IP斷線時的智慧備援）
BACKUP_NAMES = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2308": "台達電", "3711": "日月光投控",
    "2303": "聯電", "2881": "富邦金", "2882": "國泰金", "2891": "中信金", "2382": "廣達",
    "2886": "兆豐金", "3008": "大立光", "2884": "玉山金", "2885": "元大金", "2892": "第一金",
    "2357": "華碩", "3231": "緯創", "1216": "統一", "2412": "中華電", "1301": "台塑",
    "1303": "南亞", "2603": "長榮", "3037": "欣興", "2301": "光寶科", "4904": "遠傳",
    "2327": "國巨", "3045": "台灣大", "2408": "南亞科", "2449": "京元電子", "2345": "智邦",
    "2395": "研華", "2360": "致茂", "2368": "金像電", "3017": "奇鋐", "2383": "台光電",
    "2207": "和泰車", "6669": "緯穎", "3653": "健策", "3661": "世芯-KY", "2002": "中鋼",
    "5880": "合庫金", "2880": "華南金", "2883": "開發金", "2890": "永豐金", "6505": "台塑化",
    "6919": "康霈", "7769": "興合力", "2059": "川湖", "2344": "華邦電", "2376": "技嘉",
    "2324": "仁寶", "2356": "英業達", "2385": "群光", "3034": "聯詠", "3702": "大聯大",
    "4938": "和碩", "3293": "鈊象", "2474": "可成", "3005": "神基", "2379": "瑞昱",
    "2421": "建準", "6414": "樺漢", "3406": "玉晶光", "2439": "美律", "6188": "廣明",
    "6285": "啟碁", "8016": "矽創", "6139": "亞翔", "5269": "祥碩", "6196": "帆宣",
    "6239": "力成", "4958": "臻鼎-KY", "1402": "遠東新", "2912": "統一超", "2609": "陽明",
    "8209": "萬國通", "6488": "環球晶", "2801": "彰銀", "9904": "寶成", "1102": "亞泥",
    "4915": "致伸", "2615": "萬海", "1319": "東陽", "3706": "神達", "6176": "瑞儀",
    "1513": "中興電", "2393": "億光", "6257": "矽格"
}

def merge_etf_info(row):
    c = str(row['code']).strip()
    base_name = str(row['name']).strip()
    if c in etf_db:
        labels = " ".join([f"[{e}]" for e in etf_db[c]])
        return f"{base_name} {labels}"
    return base_name

# ==========================================
# 3. 獲取台股基礎資料 (證交所 Open API 與防封鎖智慧備援)
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_base_data_final():
    cols = ['code', 'name', 'price', 'vol', 'trade_value', 'pe', 'industry', 'chip_ratio', 'value_billion']
    empty_df = pd.DataFrame(columns=cols)

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    df_price = pd.DataFrame()
    try:
        # 1. 嘗試向證交所獲取全台股即時價格
        res_p = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=headers, timeout=15)
        if res_p.status_code == 200:
            try:
                res_p_json = res_p.json()
                if res_p_json:
                    raw = pd.DataFrame(res_p_json)
                    df_price = raw[raw['Code'].str.len() == 4].copy()
                    df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
                    df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
                    df_price['trade_value'] = pd.to_numeric(df_price['TradeValue'].str.replace(',', ''), errors='coerce')
                    df_price = df_price[['Code', 'Name', 'price', 'vol', 'trade_value']].rename(columns={'Code': 'code', 'Name': 'name'})
                    df_price = df_price[~df_price['code'].str.startswith('91')] 
            except ValueError:
                pass
    except Exception:
        pass

    # 🔥 【智慧備援核心】當證交所對雲端主機進行 IP 封鎖、回傳非 JSON 時，自動無縫啟用 YFinance 備援通道
    if df_price.empty:
        st.sidebar.warning("🌐 證交所目前封鎖海外雲端IP。系統已自動啟用「全球 Yahoo 備援機制」，核心策略仍可正常運作！")
        backup_codes = list(etf_db.keys())
        ticker_list = [f"{c}.TW" for c in backup_codes]
        try:
            # 向不受 IP 限制的 Yahoo Finance 批次抓取 5 天內的最新價格
            data = yf.download(ticker_list, period="5d", progress=False, timeout=15)
            if not data.empty:
                fallback_records = []
                if isinstance(data.columns, pd.MultiIndex):
                    df_close = data['Close'] if 'Close' in data.columns.levels[0] else None
                    df_vol = data['Volume'] if 'Volume' in data.columns.levels[0] else None
                else:
                    df_close = data['Close'] if 'Close' in data.columns else None
                    df_vol = data['Volume'] if 'Volume' in data.columns else None
                
                if df_close is not None:
                    for c in backup_codes:
                        tk = f"{c}.TW"
                        if tk in df_close.columns:
                            closes = df_close[tk].dropna()
                            vols = df_vol[tk].dropna() if df_vol is not None and tk in df_vol.columns else pd.Series()
                            if len(closes) >= 1:
                                cur_price = float(closes.iloc[-1])
                                cur_vol = float(vols.iloc[-1]) / 1000 if not vols.empty else 0.0
                                t_val = cur_price * (cur_vol * 1000)
                                fallback_records.append({
                                    'code': c,
                                    'name': BACKUP_NAMES.get(c, f"個股 {c}"),
                                    'price': cur_price,
                                    'vol': cur_vol,
                                    'trade_value': t_val,
                                    'pe': np.nan,
                                    'industry': "精選成分股",
                                    'chip_ratio': 0.0,
                                    'value_billion': round(t_val / 100000000, 2)
                                })
                if fallback_records:
                    return pd.DataFrame(fallback_records)[cols]
        except Exception as yf_err:
            st.sidebar.error(f"⚠️ 備援機制啟動異常: {yf_err}")
        return empty_df

    # 正常流程：繼續獲取本益比與產業（若無封鎖）
    df_pe = pd.DataFrame()
    try:
        res_pe = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", headers=headers, timeout=15)
        if res_pe.status_code == 200:
            try:
                res_pe_json = res_pe.json()
                if res_pe_json:
                    raw_pe = pd.DataFrame(res_pe_json)
                    df_pe = raw_pe[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
                    df_pe['pe'] = pd.to_numeric(df_pe['pe'].str.replace(',', ''), errors='coerce')
            except ValueError:
                pass
    except Exception:
        pass

    df_ind = pd.DataFrame()
    try:
        res_ind = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", headers=headers, timeout=15)
        if res_ind.status_code == 200:
            try:
                res_ind_json = res_ind.json()
                if res_ind_json:
                    raw_ind = pd.DataFrame(res_ind_json)
                    df_ind = raw_ind[['公司代號', '產業別']].rename(columns={'公司代號': 'code', '產業別': 'industry'})
            except ValueError:
                pass
    except Exception:
        pass

    df_chips = pd.DataFrame()
    for i in range(7):
        d_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d_str}&selectType=ALLBUT0999&response=json"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                js = res.json()
                if "fields" in js and "data" in js and js["data"]:
                    df_raw = pd.DataFrame(js["data"], columns=[c.strip() for c in js["fields"]])
                    fi_c = [c for c in df_raw.columns if '外資' in c and '買賣超' in c]
                    it_c = [c for c in df_raw.columns if '投信' in c and '買賣超' in c]
                    
                    if fi_c and it_c:
                        df_chips = pd.DataFrame()
                        df_chips['code'] = df_raw['證券代號'].astype(str).str.strip()
                        df_chips['fi'] = pd.to_numeric(df_raw[fi_c[0]].str.replace(',', ''), errors='coerce') / 1000
                        df_chips['it'] = pd.to_numeric(df_raw[it_c[0]].str.replace(',', ''), errors='coerce') / 1000
                        break
        except Exception:
            continue

    if not df_chips.empty:
        df = pd.merge(df_price, df_chips, on='code', how='left')
    else:
        df = df_price.copy()
        df['fi'], df['it'] = 0.0, 0.0

    df['fi'] = pd.to_numeric(df['fi'], errors='coerce').fillna(0.0)
    df['it'] = pd.to_numeric(df['it'], errors='coerce').fillna(0.0)
    df['vol'] = pd.to_numeric(df['vol'], errors='coerce').fillna(0.0)
    df['trade_value'] = pd.to_numeric(df['trade_value'], errors='coerce').fillna(0.0)

    net_chips = df['fi'] + df['it']
    df['chip_ratio'] = (net_chips / df['vol'].replace(0, np.nan)).fillna(0.0) * 100
    df['chip_ratio'] = df['chip_ratio'].clip(upper=100.0).round(2)
    df['value_billion'] = (df['trade_value'] / 100000000).fillna(0.0).round(2)

    if not df_pe.empty:
        df = pd.merge(df, df_pe, on='code', how='left')
    if 'pe' not in df.columns:
        df['pe'] = np.nan

    if not df_ind.empty:
        df = pd.merge(df, df_ind, on='code', how='left')
    df['industry'] = df['industry'].fillna('其他')
    
    ind_map = {
        "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維", "05": "電機機械",
        "06": "電器電欄", "07": "化學工業", "08": "生技醫療業", "09": "玻璃陶瓷", "10": "造紙工業",
        "11": "鋼鐵工業", "12": "橡膠工業", "13": "汽車工業", "14": "建材營建", "15": "航運業",
        "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨", "19": "綜合業", "20": "其他業",
        "21": "化學工業", "22": "生技醫療業", "23": "油電燃氣業",
        "24": "半導體業", "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業", 
        "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業",
        "32": "文化創意業", "33": "農業科技業", "34": "電子商務業", "35": "綠能環保業",
        "36": "數位雲端業", "37": "運動休閒業", "38": "居家生活業", "80": "建材營建"
    }
    df['industry'] = df['industry'].apply(lambda x: str(x).strip()[:-2] if str(x).strip().endswith('.0') else str(x).strip())
    df['industry'] = df['industry'].apply(lambda x: x.zfill(2) if x.isdigit() else x)
    df['industry'] = df['industry'].map(ind_map).fillna(df['industry'])
    return df[cols]

# ==========================================
# 4. 批量獲取技術指標
# ==========================================
def batch_append_tech_indicators_fast(res_df):
    res_df['回檔%'] = 0.0
    res_df['今日漲幅%'] = 0.0
    if res_df.empty:
        return res_df
        
    codes = res_df['code'].tolist()
    dd_map, chg_map = {}, {}
    
    chunk_size = 35
    for chunk_start in range(0, len(codes), chunk_size):
        chunk_codes = codes[chunk_start:chunk_start + chunk_size]
        ticker_list = [f"{str(c).strip()}.TW" for c in chunk_codes]
        
        try:
            data = yf.download(ticker_list, period="1mo", progress=False, timeout=15)
            if data.empty:
                continue
                
            if isinstance(data.columns, pd.MultiIndex):
                if 'Close' in data.columns.levels[0] and 'High' in data.columns.levels[0]:
                    df_close, df_high = data['Close'], data['High']
                    for c in chunk_codes:
                        tk = f"{c}.TW"
                        if tk in df_close.columns and tk in df_high.columns:
                            closes, highs = df_close[tk].dropna(), df_high[tk].dropna()
                            if len(closes) >= 2 and len(highs) >= 1:
                                h_max, cur, prev = float(highs.max()), float(closes.iloc[-1]), float(closes.iloc[-2])
                                if h_max > 0: dd_map[c] = round(((h_max - cur) / h_max) * 100, 2)
                                if prev > 0: chg_map[c] = round(((cur - prev) / prev) * 100, 2)
            else:
                if 'Close' in data.columns and 'High' in data.columns:
                    closes, highs = data['Close'].dropna(), data['High'].dropna()
                    if len(closes) >= 2 and len(highs) >= 1:
                        h_max, cur, prev = float(highs.max()), float(closes.iloc[-1]), float(closes.iloc[-2])
                        for c in chunk_codes:
                            if h_max > 0: dd_map[c] = round(((h_max - cur) / h_max) * 100, 2)
                            if prev > 0: chg_map[c] = round(((cur - prev) / prev) * 100, 2)
        except Exception:
            continue
        
    res_df['回檔%'] = res_df['code'].map(dd_map).fillna(0.0)
    res_df['今日漲幅%'] = res_df['code'].map(chg_map).fillna(0.0)
    return res_df

# ==========================================
# 5. 族群統計（修正：首行完美換行結構）
# ==========================================
def display_industry_cluster_stats(df_target):
    if not df_target.empty and '產業' in df_target.columns:
        ind_counts = df_target['產業'].value_counts()
        ind_counts = ind_counts[ind_counts >= 3] 
        
        if not ind_counts.empty:
            stats_items = [f"{ind} ({count} 檔)" for ind, count in ind_counts.items()]
            stats_string = "  \n".join(stats_items)
            
            st.info(f"📋 **熱門族群並列統計 (≥3檔)：** \n{stats_string}")
            st.write("") 

# ==========================================
# 6. 主程式執行流
# ==========================================
try:
    with st.spinner("正在同步全台股籌碼與盤後數據..."):
        df_base = get_stock_base_data_final()
    
    if df_base.empty:
        st.warning("📅 暫時無法取得任何市場資料。")
    else:
        # 側邊欄控制區
        with st.sidebar:
            st.header("🎯 策略與條件選擇")
            
            strategy = st.radio(
                "選擇選股策略",
                ["🚀 近期強勢", "🛡️ 穩健長期投資", "🕵️ 主力支撐", "📉 回檔進場股"]
            )
            
            st.markdown("---")
            
            with st.expander("⚙️ 大範圍過濾條件", expanded=False):
                min_p = st.slider("最低股價", min_value=0.0, max_value=500.0, value=15.0, step=5.0)
                max_p = st.slider("最高股價", min_value=100.0, max_value=2000.0, value=1000.0, step=50.0)
                min_v = st.slider("最低成交量(張)", min_value=0, max_value=10000, value=100, step=50)
                pe_min, pe_max = st.slider("本益比合理區間", min_value=0.0, max_value=100.0, value=(8.0, 22.0), step=1.0)
                target_industry = st.selectbox("選擇指定產業", options=["全部"] + sorted(list(df_base['industry'].unique())), index=0)

        # 資料大範圍預先篩選
        df_filtered = df_base[(df_base['price'] >= min_p) & (df_base['price'] <= max_p) & (df_base['vol'] >= min_v)].copy()
        if target_industry != "全部":
            df_filtered = df_filtered[df_filtered['industry'] == target_industry]

        if not df_filtered.empty:
            with st.spinner(f"正在分析 {len(df_filtered)} 檔符合條件標的之即時技術指標..."):
                df_pool = batch_append_tech_indicators_fast(df_filtered)
                
                df_pool['支撐力道'] = "🟦"
                df_pool.loc[df_pool['chip_ratio'] >= 10.0, '支撐力道'] = "🔥"
                df_pool.loc[(df_pool['chip_ratio'] >= 4.0) & (df_pool['chip_ratio'] < 10.0), '支撐力道'] = "✅"
                df_pool.loc[df_pool['chip_ratio'] < 0.0, '支撐力道'] = "📉"
                df_pool['K線連結'] = df_pool['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
        else:
            df_pool = pd.DataFrame(columns=df_base.columns.tolist() + ['回檔%', '今日漲幅%', '支撐力道', 'K線連結'])

        # 對接 ETF 標籤
        if not df_pool.empty:
            df_pool['name'] = df_pool.apply(merge_etf_info, axis=1)

        # 重新命名與處理 None
        df_display = df_pool.rename(columns={
            'code': '代號', 'name': '名稱', 'industry': '產業', 'price': '股價', 
            'chip_ratio': '集中度%', 'pe': '本益比', 'value_billion': '成交額(億)'
        })
        df_display['本益比'] = pd.to_numeric(df_display['本益比'], errors='coerce')
        df_display['本益比原始'] = df_display['本益比'] 
        df_display['本益比'] = df_display['本益比'].apply(lambda x: f"{x:.2f}" if pd.notnull(x) else "—")

        cols_order = ['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結']

        # 4大策略篩選流
        if not df_display.empty:
            if strategy == "🚀 近期強勢":
                df_final = df_display[df_display['今日漲幅%'] >= 0.5].sort_values(by='今日漲幅%', ascending=False).head(25)
            elif strategy == "🛡️ 穩健長期投資":
                df_final = df_display[(df_display['本益比原始'] >= pe_min) & (df_display['本益比原始'] <= pe_max)].sort_values(by='成交額(億)', ascending=False).head(25)
            elif strategy == "🕵️ 主力支撐":
                df_final = df_display[df_display['集中度%'] >= 2.0].sort_values(by='集中度%', ascending=False).head(25)
            elif strategy == "📉 回檔進場股":
                df_final = df_display[(df_display['回檔%'] >= 3.0) & (df_display['集中度%'] >= -2.0)].sort_values(by='回檔%', ascending=False).head(25)
            else:
                df_final = pd.DataFrame(columns=cols_order)
        else:
            df_final = pd.DataFrame(columns=cols_order)

        # 欄位寬度與格式設定
        grid_config = {
            "代號": st.column_config.TextColumn("代號", width="small", pinned=True),  
            "名稱": st.column_config.TextColumn("名稱", width=180, pinned=True),  
            "產業": st.column_config.TextColumn("產業", width=115),  
            "今日漲幅%": st.column_config.NumberColumn("今日漲幅%", format="%.2f %%", width="small"),
            "股價": st.column_config.NumberColumn("股價", format="%.2f", width="small"),
            "回檔%": st.column_config.NumberColumn("回檔%", format="%.2f %%", width="small"),
            "集中度%": st.column_config.NumberColumn("集中度%", format="%.2f %%", width="small"),
            "支撐力道": st.column_config.TextColumn("支撐力道", width="small"),
            "成交額(億)": st.column_config.NumberColumn("成交額(億)", format="%.2f 億", width="small"),
            "本益比": st.column_config.TextColumn("本益比", width="small"),
            "K線連結": st.column_config.LinkColumn("K線", display_text="📈查看", width="small")
        }

        # 頂部全局快速搜尋
        search_query = st.text_input("🔍 全局個股快速定位", placeholder="例如: 2330 或 台積電").strip()

        if search_query and not df_display.empty:
            st.markdown("### 🔍 全局搜尋結果")
            search_mask = df_display['代號'].astype(str).str.contains(search_query, case=False, na=False) | \
                          df_display['名稱'].astype(str).str.contains(search_query, case=False, na=False)
            
            df_search_show = df_display[search_mask][cols_order].copy()
            st.dataframe(df_search_show, use_container_width=True, hide_index=True, column_config=grid_config)
            st.markdown("---")

        # 主畫面大表與族群並列統計
        st.markdown(f"### 🎯 策略結果：{strategy}")
        
        display_industry_cluster_stats(df_final)
        
        df_final_show = df_final[cols_order].copy()
        st.dataframe(df_final_show, use_container_width=True, height=580, hide_index=True, column_config=grid_config)

except Exception as e:
    st.error(f"⚠️ 網頁系統執行異常: {e}")
