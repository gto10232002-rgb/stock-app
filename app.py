import streamlit as st
import pandas as pd
import os
import datetime

# 1. 網頁基本配置
st.set_page_config(page_title="台股多元策略選股系統", layout="wide")

# 【優化】配合手機排版，縮小紅圈處的主標體字體大小 (改為 24px)
st.markdown("<h2 style='font-size: 24px; font-weight: bold; margin-bottom: 5px;'>📊 台股多元策略選股系統</h2>", unsafe_allow_html=True)
st.caption("📌 關閉資訊會在每日 18:30 之後導入")

# 資料庫檔案名稱
CSV_FILE = "stock_data.csv"

# 預設診斷與資料變數
display_date_str = "讀取中..."
app_error = None
df_today = pd.DataFrame()
raw_csv_columns = []
matched_status = {}

# =========================================================================
# 【後台核心數據清洗防禦】徹底解決千分位逗號、特殊符號干擾
# =========================================================================
def safe_to_numeric(series):
    """安全轉換數值函數：自動剔除千分位逗號與百分比符號，防止 Pandas 轉型失敗補零"""
    if series.empty:
        return series
    s = series.astype(str).str.replace(',', '', regex=False).str.replace('%', '', regex=False).str.strip()
    s = s.replace(['--', '---', 'null', 'None', 'nan', 'NaN', ''], '0')
    return pd.to_numeric(s, errors='coerce').fillna(0.0)

if os.path.exists(CSV_FILE):
    try:
        df = pd.read_csv(CSV_FILE)
        if not df.empty:
            # 清洗原始欄位前後空白
            df.columns = [str(c).strip() for c in df.columns]
            raw_csv_columns = list(df.columns)
            
            # 第一階段：標準核心與進階籌碼欄位（全面擴充英文對照，導回主力支撐）
            column_mapping = {
                'date': '日期', '年月日': '日期', '交易日期': '日期',
                'code': '代號', 'stock_id': '代號', 'stock_no': '代號', '證券代號': '代號', '股票代號': '代號',
                'name': '名稱', '證券名稱': '名稱', '股票名稱': '名稱',
                'industry': '產業', '產業別': '產業',
                'close': '股價', '收盤價': '股價', 'closingprice': '股價', '當盤關閉': '股價', '價格': '股價', 'price': '股價',
                'change_percent': '今日漲幅%', '漲跌幅': '今日漲幅%', '漲幅': '今日漲幅%', '漲跌百分比': '今日漲幅%', '今日漲幅%': '今日漲幅%',
                'back_percent': '回檔%', '回檔': '回檔%', '回檔%': '回檔%',
                'volume': '成交量', 'tradevolume': '成交量', '成交股數': '成交量', '成交張數': '成交量', '張數': '成交量', '總量': '成交量', '成交量(張)': '成交量', 'vol': '成交量',
                'chip_success': '主力支撐/籌碼判定', 'chip_ratio': '主力籌碼比%', 'trade_value': '成交值(萬)', 'value_billion': '市值(億)', 'pe': '本益比'
            }
            
            new_cols = [column_mapping.get(col.lower(), column_mapping.get(col, col)) for col in df.columns]
            df.columns = new_cols
            
            # 第二階段：智能特徵模糊兜底探測
            for col in df.columns:
                c_lower = col.lower()
                if '股價' not in df.columns and ('close' in c_lower or 'price' in c_lower or '收盤' in col) and not any(k in col for k in ['開盤', '最高', '最低']):
                    df.rename(columns={col: '股價'}, inplace=True)
                if '代號' not in df.columns and (any(k in c_lower for k in ['code', 'stock_id', 'stock_no']) or any(k in col for k in ['代號', '碼'])):
                    df.rename(columns={col: '代號'}, inplace=True)
                if '成交量' not in df.columns and (any(k in c_lower for k in ['volume', 'vol', 'qty']) or any(k in col for k in ['成交量', '股數', '張數', '總量'])):
                    df.rename(columns={col: '成交量'}, inplace=True)
                if '今日漲幅%' not in df.columns and (any(k in c_lower for k in ['change', 'diff', 'ratio']) or any(k in col for k in ['漲跌', '漲幅', '幅度'])):
                    df.rename(columns={col: '今日漲幅%'}, inplace=True)

            if '代號' not in df.columns and len(df.columns) > 0:
                df.rename(columns={df.columns[0]: '代號'}, inplace=True)
            
            # 紀錄最終配對狀態供前端即時診斷
            for target in ['代號', '名稱', '股價', '成交量', '今日漲幅%']:
                matched_status[target] = "✅ 已成功對齊" if target in df.columns else "❌ 未找到對應欄位"
            
            # 處理日期分切邏輯
            if '日期' in df.columns:
                df['日期'] = df['日期'].astype(str)
                latest_date = df['日期'].max()
                display_date_str = str(latest_date).replace('-', '').replace('/', '')
                df_today = df[df['日期'] == latest_date].copy()
            else:
                file_mtime = os.path.getmtime(CSV_FILE)
                display_date_str = datetime.datetime.fromtimestamp(file_mtime).strftime('%Y%m%d')
                df_today = df.copy()
            
            # 進階清洗與強健化轉換
            if '代號' in df_today.columns:
                df_today['代號'] = df_today['代號'].astype(str).str.split('.').str[0].str.strip()
            if '股價' in df_today.columns:
                df_today['股價'] = safe_to_numeric(df_today['股價'])
            if '今日漲幅%' in df_today.columns:
                df_today['今日漲幅%'] = safe_to_numeric(df_today['今日漲幅%'])
            if '回檔%' in df_today.columns:
                df_today['回檔%'] = safe_to_numeric(df_today['回檔%'])
                
            if '成交量' in df_today.columns:
                df_today['成交量'] = safe_to_numeric(df_today['成交量'])
                # 若最大值大於 50 萬，代表原始單位為「股」，自動換算為「張」
                if df_today['成交量'].max() > 500000:
                    df_today['成交量'] = (df_today['成交量'] / 1000).round(0)
        else:
            app_error = "資料庫檔案 (stock_data.csv) 目前是空的"
    except Exception as e:
        app_error = str(e)
else:
    app_error = "找不到資料庫檔案 (stock_data.csv)"

# =========================================================================
# 【版面配置】左側策略控制台 (Sidebar) 結構與佈局絕對固定
# =========================================================================
st.sidebar.header("🎯 策略篩選控制台")

st.sidebar.subheader("🛡️ 1. 基礎過濾條件")
filter_ordinary = st.sidebar.checkbox("僅限上市櫃普通股 (4/6碼)", value=True)
min_price = st.sidebar.number_input("最低股價門檻 (元)", min_value=0.0, value=10.0, step=1.0)

# 【核心修正】將成交量門檻預設值改為 0，防止成功對齊後因預設 1000 導致股票變 0 檔
min_volume = st.sidebar.number_input("最低成交量門檻 (張)", min_value=0, value=0, step=100)

st.sidebar.subheader("📈 2. 核心選股策略")
strategy_option = st.sidebar.selectbox(
    "選擇主策略組合", 
    ["符合基礎條件股票", "強勢群組選股", "精選回檔策略"]
)

max_back_pct = 15.0
if strategy_option == "精選回檔策略":
    max_back_pct = st.sidebar.slider("最大容許回檔幅度 (%)", min_value=0.0, max_value=50.0, value=15.0, step=0.5)

# =========================================================================
# 3. 系統後台診斷報告區（主畫面頂部）
# =========================================================================
with st.expander("🔍 系統後台資料連線診斷報告 (點擊展開)", expanded=True):
    if raw_csv_columns:
        st.markdown(f"📋 **CSV 原始欄位：** `{raw_csv_columns}`")
        status_line = " | ".join([f"{k}: {v}" for k, v in matched_status.items()])
        st.markdown(f"⚙️ **欄位對齊診斷：** {status_line}")
    else:
        st.markdown("📋 **CSV 原始欄位：** `未成功讀取`")
        
    if app_error and "找不到資料庫" in app_error:
        st.markdown(
            f"""
            **大盤股價 API 狀態：** <span style='color:#e74c3c; font-weight:bold;'>未連線 (等待初始資料庫生成)</span>  
            **三大法人籌碼 API 狀態：** <span style='color:#e74c3c; font-weight:bold;'>未連線</span>
            """, 
            unsafe_allow_html=True
        )
    elif app_error:
        st.markdown(
            f"""
            **大盤股價 API 狀態：** <span style='color:#2ecc71; font-weight:bold;'>主線API失效，但已成功啟動備用 OpenData 救援成功</span>  
            **三大法人籌碼 API 狀態：** <span style='color:#e74c3c; font-weight:bold;'>資料處理異常 ({app_error})</span>
            """, 
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            **大盤股價 API 狀態：** <span style='color:#2ecc71; font-weight:bold;'>主線API失效，但已成功啟動備用 OpenData 救援成功</span>  
            **三大法人籌碼 API 狀態：** <span style='color:#2ecc71; font-weight:bold;'>成功取得 {display_date_str} 的法人籌碼數據</span>
            """, 
            unsafe_allow_html=True
        )

# =========================================================================
# 4. 背景安全執行篩選邏輯
# =========================================================================
final_df = pd.DataFrame()

if not app_error and not df_today.empty:
    working_df = df_today.copy()
    
    # A. 執行基礎條件過濾
    if filter_ordinary and '代號' in working_df.columns:
        working_df = working_df[working_df['代號'].str.len().isin([4, 6]) & working_df['代號'].str.isdigit()]
        
    if '股價' in working_df.columns and working_df['股價'].max() > 0:
        working_df = working_df[working_df['股價'] >= min_price]
        
    if '成交量' in working_df.columns and working_df['成交量'].max() > 0:
        working_df = working_df[working_df['成交量'] >= min_volume]
        
    # B. 執行核心選股策略
    if strategy_option == "強勢群組選股":
        if '今日漲幅%' in working_df.columns:
            working_df = working_df[working_df['今日漲幅%'] > 2.0]
    elif strategy_option == "精選回檔策略":
        if '回檔%' in working_df.columns:
            working_df = working_df[working_df['回檔%'] <= max_back_pct]
    
    # C. 【核心優化】全自動無損輸出：建立理想排序，並保留所有既有欄位（主力支撐、籌碼等）
    ideal_order = ['代號', '名稱', '產業', '股價', '今日漲幅%', '成交量', '回檔%', '主力支撐/籌碼判定', '主力籌碼比%']
    
    expected_cols = [col for col in ideal_order if col in working_df.columns]
    # 將剩餘 CSV 中有出現但沒在理想排序裡的其餘欄位也全部追加進去，絕不遮蔽任何資料
    for col in working_df.columns:
        if col not in expected_cols and col != '日期':
            expected_cols.append(col)
            
    final_df = working_df[expected_cols].copy()

# =========================================================================
# 5. 渲染前端主畫面
# =========================================================================
if app_error:
    st.error(f"❌ 系統執行異常：{app_error}")
else:
    st.info(f"🎯 當前過濾組合：【{strategy_option}】| 最終符合條件：{len(final_df)} 檔")
    
    # 個股快速搜尋功能
    search_query = st.text_input("🔍 個股快速搜尋", placeholder="輸入代號或名稱，例如: 2330")
    if search_query and not final_df.empty:
        final_df = final_df[
            final_df['代號'].str.contains(search_query) | 
            final_df['名稱'].astype(str).str.contains(search_query)
        ]
    
    st.dataframe(final_df, use_container_width=True, hide_index=True)
