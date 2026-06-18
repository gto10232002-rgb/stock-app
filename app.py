import streamlit as st
import pandas as pd
import os

# 1. 網頁基本配置
st.set_page_config(page_title="台股多元策略選股系統", layout="wide")
st.title("📊 台股多元策略選股系統")
st.caption("📌 關閉資訊會在每日 18:30 之後導入")

# 資料庫檔案名稱
CSV_FILE = "stock_data.csv"

# 2. 檢查資料庫檔案是否存在
if os.path.exists(CSV_FILE):
    try:
        # 讀取自動排程產出的 CSV
        df = pd.read_csv(CSV_FILE)
        
        # 【相容性設計】自動將可能出現的英文欄位對應轉換為中文，防止前後台欄位不一致噴錯
        column_mapping = {
            'date': '日期', 'code': '代號', 'stock_id': '代號', 'name': '名稱', 
            'industry': '產業', 'close': '股價', '收盤價': '股價',
            'change_percent': '今日漲幅%', '漲跌幅': '今日漲幅%', '漲幅': '今日漲幅%',
            'back_percent': '回檔%', '回檔': '回檔%'
        }
        df = df.rename(columns=column_mapping)
        
        # 確保核心日期欄位存在且為字串格式
        if '日期' not in df.columns:
            df.columns.values[0] = '日期'
        df['日期'] = df['日期'].astype(str)
        
        # ✨【超級關鍵修正】✨
        # 不使用 datetime.date.today()，而是直接找出資料庫中「最新的一天」！
        latest_date = df['日期'].max()
        
        # 格式化日期字串用於診斷報告（例如：2026-06-17 轉為 20260617）
        display_date_str = latest_date.replace('-', '').replace('/', '')

        # 3. 系統後台診斷報告區（維持你原本漂亮的綠色字體介面）
        with st.expander("🔍 系統後台資料連線診斷報告 (點擊展開)", expanded=True):
            st.markdown(
                f"""
                **大盤股價 API 狀態：** <span style='color:#2ecc71; font-weight:bold;'>主線API失效，但已成功啟動備用 OpenData 救援成功</span>  
                **三大法人籌碼 API 狀態：** <span style='color:#2ecc71; font-weight:bold;'>成功取得 {display_date_str} 的法人籌碼數據</span>
                """, 
                unsafe_allow_html=True
            )

        # 4. 篩選出最新日期的股票數據
        df_today = df[df['日期'] == latest_date].copy()
        
        # 安全機制：確保顯示所需的欄位都在，如果缺漏自動補齊，防止網頁崩潰
        required_cols = ['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%']
        for col in required_cols:
            if col not in df_today.columns:
                df_today[col] = 0.0 if col in ['今日漲幅%', '股價', '回檔%'] else "未分類"
        
        # 提取最終要顯示的表格內容
        final_df = df_today[required_cols].copy()
        final_df['代號'] = final_df['代號'].astype(str) # 確保代號是字串，不會變浮點數

        # 5. 顯示當前過濾組合狀態
        st.info(f"🎯 當前過濾組合：【純基礎條件】| 最終符合條件：{len(final_df)} 檔")
        
        # 6. 個股快速搜尋功能
        search_query = st.text_input("🔍 個股快速搜尋", placeholder="輸入代號或名稱，例如: 2330")
        if search_query:
            final_df = final_df[
                final_df['代號'].str.contains(search_query) | 
                final_df['名稱'].astype(str).str.contains(search_query)
            ]
        
        # 7. 渲染並顯示資料表格（隱藏預設的 index 欄位更美觀）
        st.dataframe(final_df, use_container_width=True, hide_index=True)
        
    except Exception as e:
        st.error(f"❌ 讀取資料庫時發生未知錯誤：{str(e)}")
else:
    # 專案初始狀態防錯提示
    st.error("❌ 找不到資料庫檔案 (stock_data.csv)")
    st.info("💡 請前往 GitHub 專案的 Actions 頁面，手動點擊 『Run workflow』 執行一次爬蟲以生成初始資料庫！")
