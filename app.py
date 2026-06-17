import streamlit as st
import pandas as pd
import numpy as np
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
# 2. 【核心改進】側邊欄表單移至最外層，確保資料異常時選單絕不消失
# ==========================================
with st.sidebar.form(key="filter_form"):
    st.header("🎯 基礎篩選條件")
    min_p = st.select_slider("最低股價", options=[0.0, 10.0, 20.0, 30.0, 50.0, 100.0, 200.0, 300.0, 500.0], value=0.0)
    max_p = st.select_slider("最高股價", options=[50.0, 100.0, 150.0, 200.0, 300.0, 400.0, 500.0, 1000.0, 2000.0, 9999.0], value=500.0)
    min_v = st.select_slider("最低成交量(張)", options=[0, 100, 500, 1000, 2000, 3000, 5000, 10000], value=1000)
    max_pe = st.select_slider("最高本益比", options=[0.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 100.0], value=30.0, format_func=lambda x: "不限" if x == 0.0 else f"{x}")
    
    st.header("🧠 進階策略加選")
    strategy_mode = st.radio("選擇進階策略模式", options=["不加選", "開啟「回檔策略」", "開啟「近期強勢群組」"], index=0)
    
    enable_drawdown = (strategy_mode == "開啟「回檔策略」")
    enable_strong = (strategy_mode == "開啟「近期強勢群組」")
    
    support_mode = st.radio("└ 籌碼支撐型態 (僅回檔策略有效)", options=["全部符合", "單日爆發強勢型", "波段洗刷接貨型"], index=0)
    dynamic_threshold = st.checkbox("└ 啟用股本規模動態門檻調整 (僅回檔策略有效)", value=True)
    min_dd = st.select_slider("└ 最低回檔幅度(%) (僅回檔策略有效)", options=[0, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50], value=5)
    min_change = st.select_slider("└ 最低今日漲幅(%) (僅近期強勢群組有效)", options=[-10, -5, -3, -1, 0, 1, 2, 3, 5, 7, 10], value=5)
    
    submit_button = st.form_submit_button(label="🚀 套用篩選條件")

# ==========================================
# 3. 獲取台股基礎資料 (內建誠實診斷報告系統)
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_base_data_v9():
    cols = ['code', 'name', 'price', 'vol', 'trade_value', 'pe', 'industry', 'chip_ratio', 'value_billion']
    empty_df = pd.DataFrame(columns=cols)
    chip_success = False
    
    # 用於回報給前端使用者的真實 API 狀態診斷書
    diagnostic_log = {"price_api": "未知異常", "chip_api": "尚未成功擷取"}

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    df_price = pd.DataFrame()
    try:
        # 【主線】TWSE OpenAPI
        res_p = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=headers, timeout=15)
        if res_p.status_code == 200:
            try:
                raw = pd.DataFrame(res_p.json())
                if not raw.empty and 'Code' in raw.columns:
                    df_price = raw.copy()
                    diagnostic_log["price_api"] = "連線成功且資料格式正確"
            except Exception:
                # 💡 核心改進：捕捉非 JSON 錯誤，直接擷取證交所回傳的網頁原始碼，抓出阻擋證據
                html_snippet = res_p.text[:120].strip().replace('\n', '')
                diagnostic_log["price_api"] = f"❌ 證交所拒絕回傳數據。伺服器回傳了網頁而非JSON (可能遭限流封鎖)。回傳片段: {html_snippet}"
        else:
            diagnostic_log["price_api"] = f"❌ 證交所主 API 伺服器異常，HTTP 狀態碼: {res_p.status_code}"
        
        # 【備用防線】傳統 Open Data 
        if df_price.empty:
            fallback_url = "https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data"
            res_fb = requests.get(fallback_url, headers=headers, timeout=15)
            if res_fb.status_code == 200:
                df_fb = pd.read_csv(StringIO(res_fb.text), dtype=str)
                if not df_fb.empty and '證券代號' in df_fb.columns:
                    df_price = df_fb.rename(columns={
                        '證券代號': 'Code', '證券名稱': 'Name',
                        '收盤價': 'ClosingPrice', '成交股數': 'TradeVolume', '成交金額': 'TradeValue'
                    })
                    diagnostic_log["price_api"] = "主線API失效，但已成功啟動備用 OpenData 救援成功"
            else:
                diagnostic_log["price_api"] += f" | 備用防線也失效，狀態碼: {res_fb.status_code}"

        if not df_price.empty:
            df_price = df_price[df_price['Code'].str.len() == 4].copy()
            df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].astype(str).str.replace(',', ''), errors='coerce')
            df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].astype(str).str.replace(',', ''), errors='coerce') / 1000
            df_price['trade_value'] = pd.to_numeric(df_price['TradeValue'].astype(str).str.replace(',', ''), errors='coerce')
            df_price = df_price[['Code', 'Name', 'price', 'vol', 'trade_value']].rename(columns={'Code': 'code', 'Name': 'name'})
            df_price = df_price[~df_price['code'].str.startswith('91')]
    except Exception as e:
        diagnostic_log["price_api"] = f"❌ 網路連線過程遭遇致命錯誤: {str(e)}"

    if df_price.empty:
        return empty_df, False, diagnostic_log

    # 獲取本益比資料
    df_pe = pd.DataFrame()
    try:
        res_pe = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", headers=headers, timeout=15)
        if res_pe.status_code == 200:
            try:
                raw_pe = pd.DataFrame(res_pe.json())
                df_pe = raw_pe[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
            except Exception:
                pass
        if df_pe.empty:
            res_pe_fb = requests.get("https://www.twse.com.tw/exchangeReport/BWIBBU_ALL?response=open_data", headers=headers, timeout=15)
            if res_pe_fb.status_code == 200:
                df_fb_pe = pd.read_csv(StringIO(res_pe_fb.text), dtype=str)
                if not df_fb_pe.empty and '證券代號' in df_fb_pe.columns:
                    df_pe = df_fb_pe[['證券代號', '本益比']].rename(columns={'證券代號': 'code', '本益比': 'pe'})
        if not df_pe.empty:
            df_pe['pe'] = pd.to_numeric(df_pe['pe'].astype(str).str.replace(',', ''), errors='coerce')
    except Exception:
        pass

    # 獲取產業別資料
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
    chip_errors = []
    for i in range(7):
        d_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d_str}&selectType=ALLBUT0999&response=json"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                try:
                    js = res.json()
                    if "data" in js:
                        df_raw = pd.DataFrame(js["data"], columns=[c.strip() for c in js["fields"]])
                        fi_c = [c for c in df_raw.columns if '外資' in c and '買賣超' in c][0]
                        it_c = [c for c in df_raw.columns if '投信' in c and '買賣超' in c][0]
                        
                        df_chips['code'] = df_raw['證券代號'].astype(str).str.strip()
                        df_chips['fi'] = pd.to_numeric(df_raw[fi_c].str.replace(',', ''), errors='coerce') / 1000
                        df_chips['it'] = pd.to_numeric(df_raw[it_c].str.replace(',', ''), errors='coerce') / 1000
                        chip_success = True
                        diagnostic_log["chip_api"] = f"成功取得 {d_str} 的法人籌碼數據"
                        break
                    else:
                        chip_errors.append(f"{d_str}(無交易數據)")
                except Exception:
                    chip_errors.append(f"{d_str}(解析JSON失敗/非預期網頁)")
            else:
                chip_errors.append(f"{d_str}(狀態碼:{res.status_code})")
        except Exception as e:
            chip_errors.append(f"{d_str}(連線異常)")
            continue
            
    if not chip_success:
        diagnostic_log["chip_api"] = f"❌ 追溯過去7天籌碼均失敗，詳細回報: {', '.join(chip_errors[:3])}"

    # 資料流合併
    if chip_success and not df_chips.empty:
        df = pd.merge(df_price, df_chips, on='code', how='left')
        df['fi'] = pd.to_numeric(df['fi'], errors='coerce').fillna(0.0)
        df['it'] = pd.to_numeric(df['it'], errors='coerce').fillna(0.0)
        net_chips = df['fi'] + df['it']
        df['chip_ratio'] = (net_chips / df['vol'].replace(0, np.nan)) * 100
        df['chip_ratio'] = df['chip_ratio'].clip(upper=100.0).round(2)
    else:
        df = df_price.copy()
        df['chip_ratio'] = np.nan 

    df['value_billion'] = (df['trade_value'] / 100000000).round(2)

    df = pd.merge(df, df_pe, on='code', how='left') if not df_pe.empty else df.assign(pe=np.nan)
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
    df['industry'] = df['industry'].map(ind_map).fillna(df['industry'])
    df['industry'] = df['industry'].apply(lambda x: '其他' if not any('\u4e00' <= c <= '\u9fff' for c in str(x)) else str(x))

    return df[cols], chip_success, diagnostic_log

# ==========================================
# ⚡ 技術指標獲取 (拒絕隱藏錯誤)
# ==========================================
def get_single_stock_tech(c):
    tk = f"{str(c).strip()}.TW"
    dd, chg = None, None  
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
    except Exception:
        pass  
    return c, dd, chg

def batch_append_tech_indicators(res_df):
    if res_df.empty:
        res_df['回檔%'] = np.nan
        res_df['今日漲幅%'] = np.nan
        return res_df, 0
    codes = res_df['code'].tolist()
    dd_map, chg_map = {}, {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(get_single_stock_tech, codes)
    
    fail_count = 0
    for c, dd, chg in results:
        dd_map[c] = dd
        chg_map[c] = chg
        if dd is None or chg is None:
            fail_count += 1
            
    res_df['回檔%'] = res_df['code'].map(dd_map)
    res_df['今日漲幅%'] = res_df['code'].map(chg_map)
    return res_df, fail_count

# ==========================================
# 4. 主網頁呈現邏輯
# ==========================================
try:
    with st.spinner("正在同步最新籌碼與產業數據..."):
        df, chip_success, diagnostic_log = get_stock_base_data_v9()
    
    # 呈現即時診斷書，讓使用者完全掌握連線狀態
    with st.expander("🔍 系統後台資料連線診斷報告 (點擊展開)", expanded=False):
        st.write(f"**大盤股價 API 狀態：** `{diagnostic_log['price_api']}`")
        st.write(f"**三大法人籌碼 API 狀態：** `{diagnostic_log['chip_api']}`")
    
    if df.empty:
        st.error(f"❌ 📅 證交所 API 未正常回傳任何大盤行情數據。原因診斷：\n`{diagnostic_log['price_api']}`\n\n請稍後再試，或檢查是否處於交易所維護時段。")
    else:
        if not chip_success:
            st.warning(f"⚠️ 【籌碼資料不完整】今日三大法人籌碼未正常回傳。原因診斷：\n`{diagnostic_log['chip_api']}`\n\n目前系統已鎖定涉及籌碼之進階選股功能，以維數據真實性。")

        # 基礎過濾
        res = df[(df['price'].notna()) & (df['vol'].notna())].copy()
        res = res[(res['price'] >= min_p) & (res['price'] <= max_p) & (res['vol'] >= min_v)]
        
        # 💡 核心安全重構：將複雜過濾條件拆開寫，絕不用單行複雜語法，避免 float 噴出 fillna 錯誤
        if max_pe > 0:
            pe_mask = (res['pe'] > 0) & (res['pe'] <= max_pe)
            pe_mask = pe_mask.fillna(False)
            res = res[pe_mask]
            
        if target_industry != "全部" if 'target_industry' in locals() else False:
            res = res[res['industry'] == target_industry]
            
        # 串接即時技術指標
        if not res.empty:
            with st.spinner(f"正在分析 {len(res)} 檔股票的即時技術指標..."):
                res, tech_fail_count = batch_append_tech_indicators(res)
            if tech_fail_count > 0:
                st.caption(f"💡 提示：當前有 {tech_fail_count} 檔個股 Yahoo Finance 連線逾時，數據暫時留白。")
        else:
            res['回檔%'] = pd.Series(dtype=float)
            res['今日漲幅%'] = pd.Series(dtype=float)

        # 執行加選策略
        if not res.empty:
            if enable_drawdown:
                if not chip_success:
                    st.error("❌ 拒絕執行策略：由於缺乏真實三大法人籌碼數據，【回檔策略】已強制停用，避免產生無效盲點。")
                    res = pd.DataFrame(columns=res.columns)
                else:
                    chip_mask = res['chip_ratio'].notna()
                    if dynamic_threshold:
                        cond_large = (res['value_billion'] >= 5.0) & (res['chip_ratio'] >= 2.5)
                        cond_small = (res['value_billion'] < 5.0) & (res['chip_ratio'] >= 5.0)
                        chip_mask = chip_mask & (cond_large | cond_small)
                    if support_mode == "單日爆發強勢型":
                        chip_mask = chip_mask & (res['chip_ratio'] >= 5.0)
                    
                    # 💡 核心安全重構：完全分離比較運算子與 fillna，防止任何 runtime 崩潰
                    dd_condition = (res['回檔%'] >= min_dd)
                    if support_mode == "波段洗刷接貨型":
                        target_dd_val = max(8.0, float(min_dd))
                        dd_condition = dd_condition & (res['回檔%'] >= target_dd_val)
                    
                    dd_mask = dd_condition.fillna(False)
                    res = res[chip_mask & dd_mask]
                    
            elif enable_strong:
                mask_strong = (res['今日漲幅%'] >= min_change).fillna(False)
                res = res[mask_strong]

        # 標記狀態文字
        if not chip_success:
            res['支撐力道'] = "❌ 缺乏籌碼數據"
        else:
            res['支撐力道'] = "🔹 觀察中"
            if not res.empty:
                res.loc[(res['chip_ratio'] >= 10.0).fillna(False), '支撐力道'] = "🔥 極強支撐"
                res.loc[((res['chip_ratio'] >= 5.0) & (res['chip_ratio'] < 10.0)).fillna(False), '支撐力道'] = "✅ 健康買盤"

        # 排序與格式化
        if not res.empty:
            if enable_strong:
                res = res.sort_values(by='今日漲幅%', ascending=False)
            else:
                res = res.sort_values(by=['chip_ratio', '回檔%'], ascending=[False, False])

        res['K線連結'] = res['code'].apply(lambda x: f"https://tw.stock.yahoo.com/quote/{x}")
        
        display_df = res.rename(columns={
            'code': '代號', 'name': '名稱', 'industry': '產業', 'price': '股價', 
            'chip_ratio': '集中度%', 'pe': '本益比', 'value_billion': '成交額(億)'
        })
        
        search_query = st.text_input("🔍 個股快速搜尋", value="", placeholder="輸入代號或名稱，例如: 2330").strip()
        if search_query and not display_df.empty:
            search_mask = display_df['代號'].astype(str).str.contains(search_query, case=False, na=False) | \
                          display_df['名稱'].astype(str).str.contains(search_query, case=False, na=False)
            display_df = display_df[search_mask]
        
        strategy_text = "回檔策略" if enable_drawdown else ("近期強勢群組" if enable_strong else "純基礎條件")
        
        if not display_df.empty:
            st.info(f"🎯 當前過濾組合：【{strategy_text}】 | **最終符合條件：{len(display_df)} 檔**")
        else:
            current_df = pd.DataFrame(columns=['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結'])
            st.info(f"🎯 當前過濾組合：【{strategy_text}】 | **最終符合條件：0 檔**")

        st.dataframe(
            display_df[['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%', '集中度%', '支撐力道', '成交額(億)', '本益比', 'K線連結']] if not display_df.empty else current_df,
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
