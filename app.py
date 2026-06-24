import streamlit as st
import pandas as pd
import requests
import datetime
import yfinance as yf

# ==========================================
# 1. 頁面配置與行動端優化樣式注入
# ==========================================
st.set_page_config(page_title="StockTool", layout="wide")

# 移除預設邊距，放大手機版可視範圍
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; padding-bottom: 0rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
    h3 { margin-top: 0rem !important; margin-bottom: 0.4rem !important; }
    .stAlert { padding: 0.5rem !important; }
</style>
""", unsafe_allow_html=True)

st.markdown("### 📊 台股多元策略選股系統 (行動優化版)")
st.caption("📌 關盤資訊會在每日 18:30 之後導入")

# ==========================================
# 2. 獲取台股基礎資料 (證交所 Open API)
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_base_data_final():
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
            df_price = df_price[~df_price['code'].str.startswith('91')] # 剔除 TDR
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
        df['fi'] = 0.0; df['it'] = 0.0

    df['fi'] = pd.to_numeric(df['fi'], errors='coerce').fillna(0.0)
    df['it'] = pd.to_numeric(df['it'], errors='coerce').fillna(0.0)
    df['vol'] = pd.to_numeric(df['vol'], errors='coerce').fillna(0.0)
    df['trade_value'] = pd.to_numeric(df['trade_value'], errors='coerce').fillna(0.0)

    net_chips = df['fi'] + df['it']
    df['chip_ratio'] = (net_chips / df['vol'].replace(0, pd.NA)).fillna(0.0) * 100
    df['chip_ratio'] = df['chip_ratio'].clip(upper=100.0).round(2)
    df['value_billion'] = (df['trade_value'] / 100000000).fillna(0.0).round(2)

    if not df_pe.empty:
        df = pd.merge(df, df_pe, on='code', how='left')
    if 'pe' not in df.columns:
        df['pe'] = pd.NA

    if not df_ind.empty:
        df = pd.merge(df, df_ind, on='code', how='left')
    df['industry'] = df['industry'].fillna('其他')

    return df[cols]

# ==========================================
# 3. 技術指標分批下載器
# ==========================================
def batch_append_tech_indicators_fast(res_df):
    res_df['回檔%'] = 0.0
    res_df['今日漲幅%'] = 0.0
    if res_df.empty:
        return res_df
        
    codes = res_df['code'].tolist()
    dd_map, chg_map = {}, {}
    chunk_size = 50
    for chunk_start in range(0, len(codes), chunk_size):
        chunk_codes = codes[chunk_start:chunk_start + chunk_size]
        ticker_list = [f"{str(c).strip()}.TW" for c in chunk_codes]
        try:
            data = yf.download(ticker_list, period="1mo", progress=False, timeout=10)
            if data.empty:
                continue
            if isinstance(data.columns, pd.MultiIndex):
                df_close, df_high = data['Close'], data['High']
                for c in chunk_codes:
                    tk = f"{c}.TW"
                    if tk in df_close.columns and tk in df_high.columns:
                        closes, highs = df_close[tk].dropna(), df_high[tk].dropna()
                        if len(closes) >= 2:
                            h_max, cur, prev = float(highs.max()), float(closes.iloc[-1]), float(closes.iloc[-2])
                            if h_max > 0: dd_map[c] = round(((h_max - cur) / h_max) * 100, 2)
                            if prev > 0: chg_map[c] = round(((cur - prev) / prev) * 100, 2)
            else:
                closes, highs = data['Close'].dropna(), data['High'].dropna()
                if len(closes) >= 2:
                    h_max, cur, prev = float(highs.max()), float(closes.iloc[-1]), float(closes.iloc[-2])
                    c = chunk_codes[0]
                    if h_max > 0: dd_map[c] = round(((h_max - cur) / h_max) * 100, 2)
                    if prev > 0: chg_map[c] = round(((cur - prev) / prev) * 100, 2)
        except Exception:
            continue
        
    res_df['回檔%'] = res_df['code'].map(dd_map).fillna(0.0)
    res_df['今日漲幅%'] = res_df['code'].map(chg_map).fillna(0.0)
    return res_df

# ==========================================
# 4. 🚀 【核心優化】手機端自定義響應式表格渲染引擎
# ==========================================
def render_mobile_responsive_table(df):
    if df.empty:
        return "<p style='color:#8a8a93; padding:12px; text-align:left;'>🔍 沒有符合此策略的個股標的。</p>"
    
    # 建立外層滾動條，以及左側 Sticky 固定、全面靠左對齊的 CSS
    html = """
    <div style="width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; background-color: #16161a; border-radius: 8px; margin-bottom: 15px; border: 1px solid #23232a;">
        <table style="width: 100%; border-collapse: collapse; text-align: right; font-size: 0.95rem; white-space: nowrap; color: #ffffff;">
            <thead>
                <tr style="background-color: #212126; color: #8a8a93; font-size: 0.8rem; border-bottom: 1px solid #2d2d35;">
                    <th style="position: sticky; left: 0; text-align: left; background-color: #212126; z-index: 3; padding: 12px 10px; width: 140px; min-width: 140px; box-shadow: 3px 0 6px rgba(0,0,0,0.4);">股票 / 特定族群</th>
                    <th style="padding: 12px 10px;">今日漲幅</th>
                    <th style="padding: 12px 10px;">股價</th>
                    <th style="padding: 12px 10px;">集中度</th>
                    <th style="padding: 12px 10px;">支撐力道</th>
                    <th style="padding: 12px 10px;">回檔幅</th>
                    <th style="padding: 12px 10px;">成交額</th>
                    <th style="padding: 12px 10px;">本益比</th>
                    <th style="padding: 12px 10px; text-align: center;">K線</th>
                </tr>
            </thead>
            <tbody>
    """
    
    for _, row in df.iterrows():
        code = row['代號']
        full_name = str(row['名稱'])
        
        # 解析特定族群標籤 (從原括號格式中分離提取)
        name_clean = full_name.split(" (")[0]
        if " (" in full_name:
            etfs = full_name.split(" (")[1].replace(")", "")
            tag_html = f'<span style="font-size: 0.7rem; padding: 1px 5px; border-radius: 4px; background-color: rgba(58, 154, 217, 0.15); color: #4fc3f7; border: 1px solid rgba(58, 154, 217, 0.3); margin-top: 3px; display: inline-block;">{etfs}</span>'
        else:
            tag_html = f'<span style="font-size: 0.7rem; padding: 1px 5px; border-radius: 4px; background-color: #2a2a30; color: #aeaea3; margin-top: 3px; display: inline-block;">{row["產業"]}</span>'

        # 漲跌幅顏色判定
        chg = row['今日漲幅%']
        chg_style = "color: #ff3b30;" if chg > 0 else ("color: #34c759;" if chg < 0 else "color: #ffffff;")
        chg_str = f"{'+' if chg > 0 else ''}{chg:.2f}%"
        
        pe_val = row['本益比']
        pe_str = f"{pe_val:.1f}" if pd.notna(pe_val) else "-"

        html += f"""
                <tr style="border-bottom: 1px solid #23232a;" ontouchstart="this.style.backgroundColor='#212126';" ontouchend="this.style.backgroundColor='transparent';">
                    <!-- 左側完全靠左固定欄位 -->
                    <td style="position: sticky; left: 0; text-align: left; background-color: #16161a; z-index: 2; padding: 12px 10px; box-shadow: 3px 0 6px rgba(0,0,0,0.4);">
                        <div style="display: flex; flex-direction: column; align-items: flex-start;">
                            <div style="display: flex; align-items: baseline; gap: 5px;">
                                <span style="font-weight: bold; color: #ffffff; font-size: 1rem;">{name_clean}</span>
                                <span style="font-size: 0.75rem; color: #8a8a93;">{code}</span>
                            </div>
                            {tag_html}
                        </div>
                    </td>
                    <!-- 右側滾動數據區 -->
                    <td style="{chg_style} font-weight: 600; padding: 12px 10px;">{chg_str}</td>
                    <td style="font-weight: 600; padding: 12px 10px;">{row['股價']:.2f}</td>
                    <td style="padding: 12px 10px;">{row['集中度%']:.2f}%</td>
                    <td style="padding: 12px 10px; font-size: 0.85rem;">{row['支撐力道']}</td>
                    <td style="padding: 12px 10px; color: #aeaea3;">{row['回檔%']:.1f}%</td>
                    <td style="padding: 12px 10px; color: #aeaea3;">{row['成交額(億)']:.1f}億</td>
                    <td style="padding: 12px 10px; color: #aeaea3;">{pe_str}</td>
                    <td style="padding: 12px 10px; text-align: center;"><a href="{row['K線連結']}" target="_blank" style="color: #4fc3f7; text-decoration: none; font-size: 0.85rem;">📈查看</a></td>
                </tr>
        """
    html += "</tbody></table></div>"
    return html

# ==========================================
# 5. 主程式架構運作
# ==========================================
try:
    with st.spinner("正在同步全台股籌碼與盤後數據..."):
        df_base = get_stock_base_data_final()
    
    if df_base.empty:
        st.warning("📅 暫時無法取得證交所開放資料，請稍後再試。")
    else:
        # 左側 Sidebar 控制項
        st.sidebar.header("⚙️ 篩選大範圍過濾")
        with st.sidebar.form(key="filter_form"):
            with st.sidebar.expander("🛠️ 點擊展開：基礎流動性門檻", expanded=False):
                min_p = st.select_slider("最低股價", options=[0.0, 10.0, 15.0, 20.0, 30.0, 50.0, 100.0, 200.0, 300.0, 500.0], value=15.0)
                max_p = st.select_slider("最高股價", options=[50.0, 100.0, 150.0, 200.0, 300.0, 400.0, 500.0, 1000.0, 2000.0, 9999.0], value=1000.0)
                min_v = st.select_slider("最低成交量(張)", options=[0, 100, 300, 500, 1000, 2000, 5000], value=500)
                target_industry = st.selectbox("選擇指定產業", options=["全部"] + sorted(list(df_base['industry'].unique())), index=0)
            
            submit_button = st.form_submit_button(label="🚀 重新整理大盤分析")

        # 數據集池處理
        df_filtered = df_base[(df_base['price'] >= min_p) & (df_base['price'] <= max_p) & (df_base['vol'] >= min_v)].copy()
        if target_industry != "全部":
            df_filtered = df_filtered[df_filtered['industry'] == target_industry]

        if not df_filtered.empty:
            with st.spinner(f"正在分析 {len(df_filtered)} 檔符合條件標的之即時技術指標..."):
                df_pool = batch_append_tech_indicators_fast(df_filtered)
                df_pool['支撐力道'] = "🔹 觀察中"
                df_pool.loc[df_pool['chip_ratio'] >= 10.0, '支撐力道'] = "🔥 極強支撐"
                df_pool.loc[(df_pool['chip_ratio'] >= 4.0) & (df_pool['chip_ratio'] < 10.0), '支撐力道'] = "✅ 健康買盤"
                df_pool['K線連結'] = df_pool['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
        else:
            df_pool = pd.DataFrame(columns=df_base.columns.tolist() + ['回檔%', '今日漲幅%', '支撐力道', 'K線連結'])

        # 🌟【特定族群歷史資料庫對照網】
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

        # 欄位映射與重新排列
        df_display = df_pool.rename(columns={
            'code': '代號', 'name': '名稱', 'industry': '產業', 'price': '股價', 
            'chip_ratio': '集中度%', 'pe': '本益比', 'value_billion': '成交額(億)'
        })

        # 分流計算四大象限策略
        if not df_display.empty:
            df_strong = df_display[df_display['今日漲幅%'] >= 0.5].sort_values(by='今日漲幅%', ascending=False).head(25)
            df_stable = df_display[(df_display['本益比'] >= 8.0) & (df_display['本益比'] <= 22.0)].sort_values(by='成交額(億)', ascending=False).head(25)
            df_chips_high = df_display[df_display['集中度%'] >= 2.0].sort_values(by='集中度%', ascending=False).head(25)
            df_drawdown = df_display[(df_display['回檔%'] >= 3.0) & (df_display['集中度%'] >= -2.0)].sort_values(by='回檔%', ascending=False).head(25)
        else:
            cols_order = ['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結']
            df_strong = pd.DataFrame(columns=cols_order)
            df_stable = pd.DataFrame(columns=cols_order)
            df_chips_high = pd.DataFrame(columns=cols_order)
            df_drawdown = pd.DataFrame(columns=cols_order)

        # 頂部全局快搜
        search_query = st.text_input("🔍 全局個股快速定位", placeholder="例如: 2330 或 台積電").strip()
        if search_query and not df_display.empty:
            st.markdown("#### 🔍 全局搜尋結果")
            search_mask = df_display['代號'].astype(str).str.contains(search_query, case=False, na=False) | \
                          df_display['名稱'].astype(str).str.contains(search_query, case=False, na=False)
            df_search_res = df_display[search_mask]
            st.markdown(render_mobile_responsive_table(df_search_res), unsafe_allow_html=True)
            st.markdown("---")

        # 行動端多群組分頁導覽
        tab1, tab2, tab3, tab4 = st.tabs([
            "🚀 1. 趨勢強勢", 
            "🛡️ 2. 穩健發展", 
            "🕵️ 3. 主力高支撐", 
            "📉 4. 回檔潛伏"
        ])
        
        with tab1:
            st.markdown(render_mobile_responsive_table(df_strong), unsafe_allow_html=True)
            
        with tab2:
            st.markdown(render_mobile_responsive_table(df_stable), unsafe_allow_html=True)
            
        with tab3:
            st.markdown(render_mobile_responsive_table(df_chips_high), unsafe_allow_html=True)
            
        with tab4:
            st.markdown(render_mobile_responsive_table(df_drawdown), unsafe_allow_html=True)

except Exception as e:
    st.error(f"⚠️ 網頁系統執行異常: {e}")
