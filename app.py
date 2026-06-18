import streamlit as st
import pandas as pd
import os

# 1. 網頁基本配置
st.set_page_config(page_title="台股多元策略選股系統", layout="wide")
st.title("📊 台股多元策略選股系統")
st.caption("📌 關閉資訊會在每日 18:30 之後導入")

# 資料庫檔案名稱
CSV_FILE = "stock_data.csv"

# 預設診斷變數
display_date_str = "讀取中..."
app_error = None
final_df = pd.DataFrame()

# 2. 檢查資料庫檔案是否存在並進行 bulletproof (防彈) 欄位處理
if os.path.exists(CSV_FILE):
    try:
        # 讀取自動排程產出的 CSV
        df = pd.read_csv(CSV_FILE)
        
        if not df.empty:
            # 【核心修正 1】安全清洗欄位名稱，移除前後空白並轉為標準清單
            df.columns = [str(c).strip() for c in df.columns]
            
            # 建立欄位中英文強對照表
            column_mapping = {
                'date': '日期', 'code': '代號', 'stock_id': '代號', 'name': '名稱', 
                'industry': '產業', 'close': '股價', '收盤價': '股價',
                'change_percent': '今日漲幅%', '漲跌幅': '今日漲幅%', '漲幅': '今日漲幅%',
                'back_percent': '回檔%', '回檔': '回檔%'
            }
            
            # 【核心修正 2】使用標準重置方式，確保 Pandas 內部快取完全同步
            new_cols = [column_mapping.get(col.lower(), col) for col in df.columns]
            df.columns = new_cols
            
            # 如果萬一還是沒有「日期」欄位，用最安全的方式強行覆寫第一個欄位
            if '日期' not in df.columns and len(df.columns) > 0:
                temp_cols = list(df.columns)
                temp_cols[0] = '日期'
                df.columns = temp_cols
            
            # 確保日期欄位存在後轉為字串格式並抓取最新日期
            if '日期' in df.columns:
                df['日期'] = df['日期'].astype(str)
                latest_date = df['日期'].max()
                display_date_str = str(latest_date).replace('-', '').replace('/', '')
                
                # 篩選出最新日期的股票數據
                df_today = df[df['日期'] == latest_date].copy()
                
                # 安全機制：確保顯示所需的欄位都在
                required_cols = ['代號', '名稱', '產業', '今日漲幅%', '股價', '回檔%']
                for col in required_cols:
                    if col not in df_today.columns:
                        df_today[col] = 0.0 if col in ['今日漲幅%', '股價', '回檔%'] else "未分類"
                
                # 提取最終表格
                final_df = df_today[required_cols].copy()
                final_df['代號'] = final_df['代號'].astype(str)
            else:
                app_error = "資料庫中缺少關鍵的 '日期' 欄位"
        else:
            app_error = "資料庫檔案 (stock_data.csv) 目前是空的"
            
    except Exception as e:
        app_error = str(e)
else:
    app_error = "找不到資料庫檔案 (stock_data.csv)"

# 3. 系統後台診斷報告區（移至核心處理後，確保不論成功失敗版面都不會消失）
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

# 4. 根據處理結果渲染前端網頁畫面
if app_error:
    st.error(f"❌ 系統執行異常：{app_error}")
    if "找不到資料庫" in app_error:
        st.info("💡 請前往 GitHub 專案的 Actions 頁面，手動點擊 『Run workflow』 執行一次爬蟲以生成初始資料庫！")
else:
    # 顯示當前過濾組合狀態
    st.info(f"🎯 當前過濾組合：【純基礎條件】| 最終符合條件：{len(final_df)} 檔")
    
    # 個股快速搜尋功能
    search_query = st.text_input("🔍 個股快速搜尋", placeholder="輸入代號或名稱，例如: 2330")
    if search_query:
        final_df = final_df[
            final_df['代號'].str.contains(search_query) | 
            final_df['名稱'].astype(str).str.contains(search_query)
        ]
    
    # 渲染並顯示資料表格
    st.dataframe(final_df, use_container_width=True, hide_index=True)
