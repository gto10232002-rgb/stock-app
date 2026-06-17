import streamlit as st
import pandas as pd
import requests
import datetime
import yfinance as yf
import concurrent.futures
from io import StringIO

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
# 2. 獲取台股基礎資料 (證交所 Open API + 官方備用機制)
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_base_data_v6():
    cols = ['code', 'name', 'price', 'vol', 'trade_value', 'pe', 'industry', 'chip_ratio', 'value_billion']
    empty_df = pd.DataFrame(columns=cols)

    # 🌟【第一道防線】共用安全的瀏覽器標頭，防止被證交所防火牆判定為惡意爬蟲而阻擋
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    df_price = pd.DataFrame()
    try:
        # 【主線方案】嘗試從 TWSE OpenAPI 抓取即時盤後行情
        res_p = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=headers, timeout=15)
        if res_p.status_code == 200:
            try:
                # 🌟【第二道防線】安全解析 JSON，避免非 JSON 回傳（如 HTML 錯誤頁面）引發系統崩潰
                raw = pd.DataFrame(res_p.json())
                if not raw.empty and 'Code' in raw.columns:
                    df_price = raw.copy()
            except ValueError:
                pass  # 解析失敗時直接交給下方的備用防線處理
        
        # 🌟【第三道防線】若主線 OpenAPI 被雲端 IP 阻擋、限流或解析失敗，則切換至證交所官方傳統 Open Data 備用機制 (CSV 格式)
        if df_price.empty:
            fallback_url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data"
            res_fb = requests.get(fallback_url, headers=headers, timeout=15)
            if res_fb.status_code == 200:
                df_fb = pd.read_csv(StringIO(res_fb.text), dtype=str)
                if not df_fb.empty and '證券代號' in df_fb.columns:
                    # 將傳統網頁欄位名稱對齊 OpenAPI 欄位格式，以利後續邏輯無縫接軌
                    df_price = df_fb.rename(columns={
                        '證券代號': 'Code',
                        '證券名稱': 'Name',
                        '收盤價': 'ClosingPrice',
                        '成交股數': 'TradeVolume',
                        '成交金額': 'TradeValue'
                    })

        # 開始處理收集到的股價數據
        if not df_price.empty:
            df_price = df_price[df_price['Code'].str.len() == 4].copy()
            df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].astype(str).str.replace(',', ''), errors='coerce')
            df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].astype(str).str.replace(',', ''), errors='coerce') / 1000
            df_price['trade_value'] = pd.to_numeric(df_price['TradeValue'].astype(str).str.replace(',', ''), errors='coerce')
            df_price = df_price[['Code', 'Name', 'price', 'vol', 'trade_value']].rename(columns={'Code': 'code', 'Name': 'name'})
            
            # 源頭全面封殺所有 91 開頭的存託憑證(TDR)
            df_price = df_price[~df_price['code'].str.startswith('91')]
    except Exception as e:
        st.sidebar.error(f"⚠️ 股價API異常: {e}")

    if df_price.empty:
        return empty_df

    # 獲取本益比資料 (同樣配置主線與備用雙軌防線機制)
    df_pe = pd.DataFrame()
    try:
        res_pe = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", headers=headers, timeout=15)
        if res_pe.status_code == 200:
            try:
                raw_pe = pd.DataFrame(res_pe.json())
                df_pe = raw_pe[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
            except Exception:
                pass
                
        # 本益比備用防線 (CSV 機制)
        if df_pe.empty:
            res_pe_fb = requests.get("https://www.twse.com.tw/exchangeReport/BWIBBU_ALL?response=open_data", headers=headers, timeout=15)
            if res_pe_fb.status_code == 200:
                df_pe_fb = pd.read_csv(StringIO(res_pe_fb.text), dtype=str)
                if not df_pe_fb.empty and '證券代號' in df_pe_fb.columns:
                    df_pe = df_pe_fb[['證券代號', '本益比']].rename(columns={'證券代號': 'code', '本益比': 'pe'})

        if not df_pe.empty:
            df_pe['pe'] = pd.to_numeric(df_pe['pe'].astype(str).str.replace(',', ''), errors='coerce')
    except Exception:
        pass

    # 獲取產業別資料 (補齊 Headers 避免被擋)
    df_ind = pd.DataFrame()
    try:
        res_ind = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", headers=headers, timeout=15)
        if res_ind.status_code == 200:
            try:
                raw_ind = pd.DataFrame(res_ind.json())
                df_ind = raw_ind[['公司代號', '產業別']].rename(columns={'公司代號': 'code', '產業別': 'industry'})
            except Exception:
                pass
    except Exception:
        pass

    # 獲取三大法人籌碼資料
    df_chips = pd.DataFrame()
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

    # 資料合併與指標計算
    df = pd.merge(df_price, df_chips, on='code', how='left') if not df_chips.empty else df_price.copy()
    
    df['fi'] = pd.to_numeric(df.get('fi', 0.0), errors='coerce').fillna(0.0)
    df['it'] = pd.to_numeric(df.get('it', 0.0), errors='coerce').fillna(0.0)
    df['vol'] = pd.to_numeric(df.get('vol', 0.0), errors='coerce').fillna(0.0)
    df['trade_value'] = pd.to_numeric(df.get('trade_value', 0.0), errors='coerce').fillna(0.0)

    net_chips = df['fi'] + df['it']
    df['chip_ratio'] = (net_chips / df['vol'].replace(0, pd.NA)).fillna(0.0) * 100
    df['chip_ratio'] = df['chip_ratio'].clip(upper=100.0).round(2)
    df['value_billion'] = (df['trade_value'] / 100000000).fillna(0.0).round(2)

    df = pd.merge(df, df_pe, on='code', how='left') if not df_pe.empty else df.assign(pe=pd.NA)
    df = pd.merge(df, df_ind, on='code', how='left') if not df_ind.empty else df.assign(industry='其他')
    
    ind_map = {
        "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維", "05": "電機機械",
        "06": "電器電纜", "07": "化學工業", "08": "生技醫療業", "09": "玻璃陶瓷", "10": "造紙工業",
        "11": "鋼鐵工業", "12": "橡膠工業", "13": "汽車工業", "14": "建材營建", "15": "航運業",
        "16": "觀光餐旅", "17": "金融保險", "18": "貿易百貨", "19": "綜合業", "20": "其他業",
        "21": "化學工業", "22": "生技醫療業", "23": "油電燃氣業",
        "24": "半導體業", "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業", 
        "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業",
        "32": "文化創意業", "33": "農業科技業", "34": "電子商務業", "35": "綠能環保業",
        "36": "數位雲端業", "37": "運動休閒業", "38": "居家生活業",
        "80": "建材營建", "91": "存託憑證"
    }
    
    def to_clean_code(x):
        s = str(x).strip()
        if s.endswith('.0'):  
            s = s[:-2]
        if s.isdigit():       
            return s.zfill(2)
        return s

    df['industry'] = df['industry'].apply(to_clean_code)
    df['industry'] = df['industry'].map(ind_map).fillna(df['industry'])
    
    def force_remove_numeric_code(x):
        s = str(x).strip()
        if not s or s.lower() in ['nan', 'none']:
            return '其他'
        if not any('\u4e00' <= char <= '\u9fff' for char in s):
            return '其他'
        return s
        
    df['industry'] = df['industry'].apply(force_remove_numeric_code)

    return df[cols]

# ==========================================
# ⚡ 高速多執行緒獲取技術指標
# ==========================================
def get_single_stock_tech(c):
    tk = f"{str(c).strip()}.TW"
    dd, chg = 0.0, 0.0
    try:
        hist = yf.download(tk, period="1mo", progress=False, timeout=10)
        if not hist.empty and 'Close' in hist.columns and 'High' in hist.columns:
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = [col[0] for col in hist.columns]
                
            closes = hist['Close'].dropna()
            highs = hist['High'].dropna()
            if len(closes) >= 2:
                h_max = float(highs.max())
                cur = float(closes.iloc[-1])
                prev = float(closes.iloc[-2])
                if h_max > 0: dd = round(((h_max - cur) / h_max) * 100, 2)
                if prev > 0: chg = round(((cur - prev) / prev) * 100, 2)
    except Exception as e:
        pass
    return c, dd, chg

def batch_append_tech_indicators(res_df):
    if res_df.empty:
        res_df['回檔%'] = 0.0
        res_df['今日漲幅%'] = 0.0
        return res_df

    codes = res_df['code'].tolist()
    dd_map, chg_map = {}, {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(get_single_stock_tech, codes)
        
    for c, dd, chg in results:
        dd_map[c] = dd
        chg_map[c] = chg

    res_df['回檔%'] = res_df['code'].map(dd_map).fillna(0.0)
    res_df['今日漲幅%'] = res_df['code'].map(chg_map).fillna(0.0)
    return res_df

# ==========================================
# 3. 主程式邏輯
# ==========================================
try:
    with st.spinner("正在同步最新籌碼與產業數據..."):
        df = get_stock_base_data_v6()
    
    if df.empty:
        st.warning("📅 暫時無法從證交所取得完整即時資料。請確認網路連線或是否為非交易時間。")
    else:
        with st.sidebar.form(key="filter_form"):
            st.header("🎯 基礎篩選條件")
            
            min_p = st.select_slider("最低股價", options=[0.0, 10.0, 20.0, 30.0, 50.0, 100.0, 200.0, 300.0, 500.0], value=0.0)
            max_p = st.select_slider("最高股價", options=[50.0, 100.0, 150.0, 200.0, 300.0, 400.0, 500.0, 1000.0, 2000.0, 9999.0], value=500.0)
            min_v = st.select_slider("最低成交量(張)", options=[0, 100, 500, 1000, 2000, 3000, 5000, 10000], value=1000)
            max_pe = st.select_slider("最高本益比", options=[0.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 100.0], value=30.0, format_func=lambda x: "不限" if x == 0.0 else f"{x}")
            
            with st.expander("📂 點擊展開：篩選特定產業", expanded=False):
                target_industry = st.radio("選擇產業", options=["全部"] + sorted(list(df['industry'].unique())), index=0)
            
            st.header("🧠 進階策略加選")
            strategy_mode = st.radio("選擇進階策略模式", options=["不加選", "開啟「回檔策略」", "開啟「近期強勢群組」"], index=0)
            
            enable_drawdown = (strategy_mode == "開啟「回檔策略」")
            enable_strong = (strategy_mode == "開啟「近期強勢群組」")
            
            support_mode = st.radio("└ 籌碼支嚀型態 (僅回檔策略有效)", options=["全部符合", "單日爆發強勢型", "波段洗刷接貨型"], index=0)
            dynamic_threshold = st.checkbox("└ 啟用股本規模動態門檻調整 (僅回檔策略有效)", value=True)
            
            min_dd = st.select_slider("└ 最低回檔幅度(%) (僅回檔策略有效)", options=[0, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50], value=5)
            min_change = st.select_slider("└ 最低今日漲幅(%) (僅近期強勢群組有效)", options=[-10, -5, -3, -1, 0, 1, 2, 3, 5, 7, 10], value=5)
            
            submit_button = st.form_submit_button(label="🚀 套用篩選條件")
        
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
                res = res[sub_mask]
                
            elif enable_strong:
                mask_strong = (res['今日漲幅%'] >= min_change)
                res = res[mask_strong]

        res['支撐力道'] = "🔹 觀察中"
        if not res.empty:
            res.loc[res['chip_ratio'] >= 10.0, '支撐力道'] = "🔥 極強支撐"
            res.loc[(res['chip_ratio'] >= 5.0) & (res['chip_ratio'] < 10.0), '支撐力道'] = "✅ 健康買盤"
            
            if enable_strong:
                res = res.sort_values(by='今日漲幅%', ascending=False)
            else:
                res = res.sort_values(by=['chip_ratio', '回檔%'], ascending=[False, False])

        res['K線連結'] = res['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
        
        # ETF 資料庫對照
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
        
        # 🔍 精簡安全的個股快速搜尋框
        search_query = st.text_input(
            "🔍 個股快速搜尋 (支援輸入股票代號或中文名稱)", 
            value="", 
            placeholder="請在此輸入代號或名稱，例如: 2330 或 台積電"
        ).strip()
        
        if search_query and not display_df.empty:
            search_mask = display_df['代號'].astype(str).str.contains(search_query, case=False, na=False) | \
                          display_df['名稱'].astype(str).str.contains(search_query, case=False, na=False)
            display_df = display_df[search_mask]
        
        if enable_drawdown:
            strategy_text = "回檔策略"
        elif enable_strong:
            strategy_text = "近期強勢群組"
        else:
            strategy_text = "純基礎條件"
            
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
        
        # 📊 穩定繪製資料表
        st.dataframe(
            current_df[['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結']],
            column_config={
                "代號": st.column_config.TextColumn("代號"),  
                "名稱": st.column_config.TextColumn("名稱"),  
                "產業": st.column_config.TextColumn("產業"),
                "今日漲幅%": st.column_config.NumberColumn("今日漲幅%", format="%.2f %%"),
                "股價": st.column_config.NumberColumn("股價", format="%.2f"),
                "回檔%": st.column_config.NumberColumn("回檔%", format="%.2f %%"),
                "集中度%": st.column_config.NumberColumn("集中度%", format="%.2f %%"),
                "支撐力道": st.column_config.TextColumn("支撐力道"),
                "成交額(億)": st.column_config.NumberColumn("成交額(億)", format="%.2f 億"),
                "本益比": st.column_config.NumberColumn("本益比", format="%.2f"),
                "K線連結": st.column_config.LinkColumn("K線", display_text="📈查看")
            },
            use_container_width=True,
            hide_index=True,
            height=650
        )

except Exception as e:
    st.error(f"⚠️ 網頁系統執行異常: {e}")
