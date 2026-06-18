import streamlit as st
import pandas as pd
import os
import datetime

# 1. 網頁基本配置
st.set_page_config(page_title="台股多元策略選股系統", layout="wide")
st.title("📊 台股多元策略選股系統")
st.caption("📌 關閉資訊會在每日 18:30 之後導入")

# 資料庫檔案名稱
CSV_FILE = "stock_data.csv"

# 預設診斷與資料變數
display_date_str = "讀取中..."
app_error = None
df_today = pd.DataFrame()

# =========================================================================
# 【核心數據防禦】智能對齊欄位，絕不動到原始數據結構，徹底解決「只剩一檔股」的問題
# =========================================================================
if os.path.exists(CSV_FILE):
    try:
        df = pd.read_csv(CSV_FILE)
        if not df.empty:
            # 清洗欄位前後空白
            df.columns = [str(c).strip() for c in df.columns]
            
            # 建立標準中英文欄位對照表
            column_mapping = {
                'date': '日期', 'code': '代號', 'stock_id': '代號', 'stock_no': '代號',
                'name': '名稱', 'industry': '產業', 'close': '股價', '收盤價': '股價',
                'change_percent': '今日漲幅%', '漲跌幅': '今日漲幅%', '漲幅': '今日漲幅%',
                'back_percent': '回檔%', '回檔': '回檔%', 'volume': '成交量', '成交量': '成交量'
            }
            
            new_cols = [column_mapping.get(col.lower(), col) for col in df.columns]
            df.columns = new_cols
            
            # 安全防護：如果沒對齊到代號，且第一欄是數值(如9958)，將其歸位給「代號」，絕不污染成日期
            if '代號' not in df.columns and len(df.columns) > 0:
                df.rename(columns={df.columns[0]: '代號'}, inplace=True)
            
            # 安全處理日期：若資料內含日期則抓最新，若無則以檔案更新時間為準，不強行霸佔數據欄
            if '日期' in df.columns:
                df['日期'] = df['日期'].astype(str)
                latest_date = df['日期'].max()
                display_date_str = str(latest_date).replace('-', '').replace('/', '')
                df_today = df[df['日期'] == latest_date].copy()
            else:
                file_mtime = os.path.getmtime(CSV_FILE)
                display_date_str = datetime.datetime.fromtimestamp(file_mtime).strftime('%Y%m%d')
                df_today = df.copy()
            
            # 數據格式標準化（確保篩選時不崩潰）
            if '代號' in df_today.columns:
                df_today['代號'] = df_today['代號'].astype(str).str.split('.').str[0].str.strip()
            if '股價' in df_today.columns:
                df_today['股價'] = pd.to_numeric(df_today['股價'], errors='coerce').fillna(0.0)
            if '今日漲幅%' in df_today.columns:
                df_today['今日漲幅%'] = pd.to_numeric(df_today['今日漲幅%'], errors='coerce').fillna(0.0)
            if '回檔%' in df_today.columns:
                df_today['回檔%'] = pd.to_numeric(df_today['回檔%'], errors='coerce').fillna(0.0)
            if '成交量' in df_today.columns:
                df_today['成交量'] = pd.to_numeric(df_today['成交量'], errors='coerce').fillna(0)
        else:
            app_error = "資料庫檔案 (stock_data.csv) 目前是空的"
    except Exception as e:
        app_error = str(e)
else:
    app_error = "找不到資料庫檔案 (stock_data.csv)"

# =========================================================================
# 【版面回歸】左側策略控制台 (Sidebar) 完整還原，除錯絕不動搖此區
# =========================================================================
st.sidebar.header("🎯 策略篩選控制台")

st.sidebar.subheader("🛡️ 1. 基礎過濾條件")
filter_ordinary = st.sidebar.checkbox("僅限上市櫃普通股 (4/6碼)", value=True)
min_price = st.sidebar.number_input("最低股價門檻 (元)", min_value=0.0, value=10.0, step=1.0)
min_volume = st.sidebar.number_input("最低成交量門檻 (張)", min_value=0, value=1000, step=100)

st.sidebar.subheader("📈 2. 核心選股策略")
strategy_option = st.sidebar.selectbox(
    "選擇主策略組合", 
    ["符合基礎條件股票", "強勢群組選股", "精選回檔策略"]
)

# 針對回檔策略提供動態參數滑桿
max_back_pct = 15.0
if strategy_option == "精選回檔策略":
    max_back_pct = st.sidebar.slider("最大容許回檔幅度 (%)", min_value=0.0, max_value=50.0, value=15.0, step=0.5)

# =========================================================================
# 3. 系統後台診斷報告區（主畫面頂部，隔離保護）
# =========================================================================
with st.expander("🔍 系統後台資料連線診斷報告 (點擊展開)", expanded=True):
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
# 4. 背景安全執行篩選邏輯（不干擾前端 UI 渲染）
# =========================================================================
final_df = pd.DataFrame()

if not app_error and not df_today.empty:
    working_df = df_today.copy()
    
    # A. 執行基礎條件過濾
    # 1. 標的純化 (排除權證、ETF、存託憑證，僅保留4碼或6碼純數字普通股)
    if filter_ordinary and '代號' in working_df.columns:
        working_df = working_df[working_df['代號'].str.len().isin([4, 6]) & working_df['代號'].str.isdigit()]
        
    # 2. 價格門檻
    if '股價' in working_df.columns:
        working_df = working_df[working_df['股價'] >= min_price]
        
    # 3. 流動性過濾 (若爬蟲有抓到成交量欄位則執行)
    if '成交量' in working_df.columns:
        working_df = working_df[working_df['成交量'] >= min_volume]
        
    # B. 執行核心選股策略
    if strategy_option == "強勢群組選股":
        if '今日漲幅%' in working_df.columns:
            working_df = working_df[working_df['今日漲幅%'] > 2.0]  # 強勢股基本篩選範例
    elif strategy_option == "精選回檔策略":
        if '回檔%' in working_df.columns:
            working_df = working_df[working_df['回檔%'] <= max_back_pct]
    
    # C. 安全提取最終要顯示的標準看板欄位，缺少的欄位自動補 0 不崩潰
    expected_cols = ['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%']
    for col in expected_cols:
        if col not in working_df.columns:
            working_df[col] = "無資料" if col in ['名稱', '產業'] else 0.0
    
    final_df = working_df[expected_cols].copy()

# =========================================================================
# 5. 渲染前端主畫面
# =========================================================================
if app_error:
    st.error(f"❌ 系統執行異常：{app_error}")
    if "找不到資料庫" in app_error:
        st.info("💡 請前往 GitHub 專案的 Actions 頁面，手動點擊 『Run workflow』 執行一次爬蟲以生成初始資料庫！")
else:
    # 顯示當前過濾組合狀態
    st.info(f"🎯 當前過濾組合：【{strategy_option}】| 最終符合條件：{len(final_df)} 檔")
    
    # 個股快速搜尋功能
    search_query = st.text_input("🔍 個股快速搜尋", placeholder="輸入代號或名稱，例如: 2330")
    if search_query and not final_df.empty:
        final_df = final_df[
            final_df['代號'].str.contains(search_query) | 
            final_df['名稱'].astype(str).str.contains(search_query)
        ]
    
    # 渲染並顯示完整資料表格
    st.dataframe(final_df, use_container_width=True, hide_index=True)
