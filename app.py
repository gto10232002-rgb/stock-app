import streamlit as st
import pandas as pd
import requests
import datetime
import yfinance as yf
import concurrent.futures

# ==========================================
# 1. 頁面配置與 CSS
# ==========================================
st.set_page_config(page_title="StockTool", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2.2rem !important; padding-bottom: 0rem !important; }
    h3 { margin-top: 0rem !important; margin-bottom: 0.4rem !important; }
    .stAlert { padding: 0.6rem !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📊 台股多元策略選股系統 (四大象限觀測版)")
st.caption("📌 關盤資訊會在每日 18:30 之後導入")

# ==========================================
# 2. 獲取台股基礎資料 (證交所 Open API)
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_base_data_v9():
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
            
            # 🌟【嚴守策略】源頭全面封殺所有 91 開頭的存託憑證(TDR)
            df_price = df_price[~df_price['code'].str.startswith('91')]
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
        "36": "數位雲端業", "37": "運動休閒業", "38": "居家生活業", "80": "建材營建"
    }
    
    df['industry'] = df['industry'].apply(lambda x: str(x).strip()[:-2] if str(x).strip().endswith('.0') else str(x).strip())
    df['industry'] = df['industry'].apply(lambda x: x.zfill(2) if x.isdigit() else x)
    df['industry'] = df['industry'].map(ind_map).fillna(df['industry'])
    df['industry'] = df['industry'].apply(lambda x: x if any('\u4e00' <= char <= '\u9fff' for char in str(x)) else '其他')

    return df[cols]

# ==========================================
# ⚡ 【核心修正】技術指標安全獲取函式
# ==========================================
def get_single_stock_tech_safe(c):
    tk = f"{str(c).strip()}.TW"
    dd, chg = 0.0, 0.0
    try:
        stock = yf.Ticker(tk)
        hist = stock.history(period="1mo")
        if not hist.empty:
            # 💡 關鍵安全防護：將潛在的 MultiIndex 欄位扁平化，確保能精準取值
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = [col[0] for col in hist.columns]
            
            if 'Close' in hist.columns and 'High' in hist.columns:
                closes = hist['Close'].dropna()
                highs = hist['High'].dropna()
                if len(closes) >= 2:
                    h_max = float(highs.max())
                    cur = float(closes.iloc[-1])
                    prev = float(closes.iloc[-2])
                    if h_max > 0: dd = round(((h_max - cur) / h_max) * 100, 2)
                    if prev > 0: chg = round(((cur - prev) / prev) * 100, 2)
    except Exception:
        pass
    return c, dd, chg

def batch_append_tech_indicators(res_df):
    if res_df.empty:
        res_df['回檔%'] = 0.0
        res_df['今日漲幅%'] = 0.0
        return res_df
    codes = res_df['code'].tolist()
    dd_map, chg_map = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(get_single_stock_tech_safe, codes)
    for c, dd, chg in results:
        dd_map[c], chg_map[c] = dd, chg
    res_df['回檔%'] = res_df['code'].map(dd_map).fillna(0.0)
    res_df['今日漲幅%'] = res_df['code'].map(chg_map).fillna(0.0)
    return res_df

# ==========================================
# 3. 主程式邏輯
# ==========================================
try:
    with st.spinner("正在同步全台股籌碼與盤後數據..."):
        df_base = get_stock_base_data_v9()
    
    if df_base.empty:
        st.warning("📅 暫時無法取得證交所資料。")
    else:
        # 📌 左側控制列
        st.sidebar.header("⚙️ 篩選大範圍過濾")
        
        with st.sidebar.form(key="filter_form"):
            # 🌟【優化亮點】細部參數依然嚴格保持折疊隱藏，防止手殘誤觸
            with st.expander("🛠️ 點擊展開：基礎流動性門檻", expanded=False):
                min_p = st.select_slider("最低股價", options=[0.0, 10.0, 20.0, 30.0, 50.0, 100.0, 200.0, 300.0, 500.0], value=15.0)
                max_p = st.select_slider("最高股價", options=[50.0, 100.0, 150.0, 200.0, 300.0, 400.0, 500.0, 1000.0, 2000.0, 9999.0], value=1000.0)
                min_v = st.select_slider("最低成交量(張)", options=[0, 100, 300, 500, 1000, 2000, 5000], value=500)
                target_industry = st.selectbox("選擇指定產業", options=["全部"] + sorted(list(df_base['industry'].unique())), index=0)
            
            st.markdown("💡 *設定流動性門檻後，點擊下方按鈕即可同步計算四大象限。*")
            submit_button = st.form_submit_button(label="🚀 重新整理大盤分析")

        # 基礎池過濾 (只看有流動性的標的)
        df_pool = df_base[(df_base['price'] >= min_p) & (df_base['price'] <= max_p) & (df_base['vol'] >= min_v)].copy()
        if target_industry != "全部":
            df_pool = df_pool[df_pool['industry'] == target_industry]

        # 批次計算技術指標
        if not df_pool.empty:
            with st.spinner(f"正在分析 {len(df_pool)} 檔符合流動性標的之即時技術指標..."):
                df_pool = batch_append_tech_indicators(df_pool)
        else:
            df_pool['回檔%'] = pd.Series(dtype=float)
            df_pool['今日漲幅%'] = pd.Series(dtype=float)

        # 支撐力道判定
        df_pool['支撐力道'] = "🔹 觀察中"
        if not df_pool.empty:
            df_pool.loc[df_pool['chip_ratio'] >= 10.0, '支撐力道'] = "🔥 極強支撐"
            df_pool.loc[(df_pool['chip_ratio'] >= 4.0) & (df_pool['chip_ratio'] < 10.0), '支撐力道'] = "✅ 健康買盤"

        # 🌟【完整對照】原本定義的 ETF 歷史資料庫
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

        if not df_pool.empty:
            df_pool['name'] = df_pool.apply(merge_etf_info, axis=1)

        # 產生 Yahoo 財經 K 線連結
        df_pool['K線連結'] = df_pool['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")

        # 重命名欄位供顯示
        df_display = df_pool.rename(columns={
            'code': '代號', 'name': '名稱', 'industry': '產業', 'price': '股價', 
            'chip_ratio': '集中度%', 'pe': '本益比', 'value_billion': '成交額(億)'
        })

        # ==========================================
        # 🧠 策略核心：四大象限並行分流與排序
        # ==========================================
        
        # 1. 🚀 趨勢強勢股群組 (今日正報酬前茅 + 多頭帶動)
        df_strong = df_display[df_display['今日漲幅%'] >= 0.5].sort_values(by='今日漲幅%', ascending=False).head(25)
        
        # 2. 🛡️ 穩健發展股群組 (合理本益比 8-22 倍 + 依成交金額排序)
        df_stable = df_display[(df_display['本益比'] >= 8.0) & (df_display['本益比'] <= 22.0)].sort_values(by='成交額(億)', ascending=False).head(25)
        
        # 3. 🕵️ 主力高支撐股群組 (籌碼高集中度 + 依法人買氣排序)
        df_chips_high = df_display[df_display['集中度%'] >= 2.0].sort_values(by='集中度%', ascending=False).head(25)
        
        # 4. 📉 回檔進場股群組 (從月高點回檔達 3.0% 以上 + 主力無大撤退)
        df_drawdown = df_display[(df_display['回檔%'] >= 3.0) & (df_display['集中度%'] >= -2.0)].sort_values(by='回檔%', ascending=False).head(25)

        # 🌟 頂部搜尋框
        search_query = st.text_input("🔍 全局個股快速定位 (輸入代號或名稱可直接在大盤池中尋找)", placeholder="例如: 2330 或 台積電").strip()
        
        # 定義顯示欄位順序（確保包含K線連結）
        cols_order = ['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結']
        
        # 設定通用表格格式組態
        grid_config = {
            "代號": st.column_config.TextColumn("代號", pinned=True),  
            "名稱": st.column_config.TextColumn("名稱", pinned=True),  
            "產業": st.column_config.TextColumn("產業"),
            "今日漲幅%": st.column_config.NumberColumn("今日漲幅%", format="%.2f %%"),
            "股價": st.column_config.NumberColumn("股價", format="%.2f"),
            "回檔%": st.column_config.NumberColumn("回檔%", format="%.2f %%"),
            "集中度%": st.column_config.NumberColumn("集中度%", format="%.2f %%"),
            "支撐力道": st.column_config.TextColumn("支撐力道"),
            "成交額(億)": st.column_config.NumberColumn("成交額(億)", format="%.2f 億"),
            "本益比": st.column_config.NumberColumn("本益比", format="%.2f"),
            "K線連結": st.column_config.LinkColumn("K線", display_text="📈查看")
        }

        if search_query:
            st.markdown("### 🔍 全局搜尋結果")
            search_mask = df_display['代號'].astype(str).str.contains(search_query, case=False, na=False) | \
                          df_display['名稱'].astype(str).str.contains(search_query, case=False, na=False)
            st.dataframe(df_display[search_mask][cols_order], use_container_width=True, hide_index=True, column_config=grid_config)
            st.markdown("---")

        # 🌟 用 Tabs 分頁呈現四大策略
        tab1, tab2, tab3, tab4 = st.tabs([
            "🚀 1. 趨勢強勢股", 
            "🛡️ 2. 穩健發展股", 
            "🕵️ 3. 主力高支撐股", 
            "📉 4. 回檔進場股"
        ])
        
        with tab1:
            st.subheader("🔥 趨勢強勢標的 (依今日漲幅排序)")
            if not df_strong.empty:
                st.dataframe(df_strong[cols_order], use_container_width=True, hide_index=True, height=550, column_config=grid_config)
            else:
                st.info("暫無符合強勢動能條件之標的。")
            
        with tab2:
            st.subheader("💎 穩健發展標的 (合理本益比精選)")
            if not df_stable.empty:
                st.dataframe(df_stable[cols_order], use_container_width=True, hide_index=True, height=550, column_config=grid_config)
            else:
                st.info("暫無符合穩健估值區間之標的。")
            
        with tab3:
            st.subheader("💪 主力籌碼吸貨標的 (依法人集中度排序)")
            if not df_chips_high.empty:
                st.dataframe(df_chips_high[cols_order], use_container_width=True, hide_index=True, height=550, column_config=grid_config)
            else:
                st.info("暫無主力顯著吸貨之標的。")
            
        with tab4:
            st.subheader("🛒 修正回檔潛伏標的 (依高點回檔幅度排序)")
            if not df_drawdown.empty:
                st.dataframe(df_drawdown[cols_order], use_container_width=True, hide_index=True, height=550, column_config=grid_config)
            else:
                st.info("暫無符合回檔修正幅度之標的。")

except Exception as e:
    st.error(f"⚠️ 網頁系統執行異常: {e}")
