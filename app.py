import streamlit as st
import pandas as pd
import requests
import datetime
import time
import yfinance as yf

# ... (前面的 base_data 函式維持不變) ...

# ⚡ 優化技術指標撈取：改為批次分段下載，防止被封鎖
def get_technical_data_batch(valid_codes, batch_size=50):
    all_data = pd.DataFrame()
    ticker_list = [f"{c}.TW" for c in valid_codes]
    
    # 分批次下載
    for i in range(0, len(ticker_list), batch_size):
        batch = ticker_list[i:i + batch_size]
        try:
            # 增加一些穩定參數
            batch_data = yf.download(batch, period="1mo", threads=True, progress=False)
            if not batch_data.empty:
                if all_data.empty:
                    all_data = batch_data
                else:
                    # 簡單合併欄位
                    all_data = pd.concat([all_data, batch_data], axis=1)
            time.sleep(1) # 每一組請求後休息一秒，這對穩定性非常重要
        except Exception as e:
            continue
    return all_data

# ... (將原來的 hist_data = yf.download(...) 那行替換為) ...

# 替換掉原本那段下載邏輯：
if not res.empty and (enable_drawdown or enable_strong):
    with st.spinner(f"正在分批抓取 {len(res)} 檔股票的即時行情..."):
        valid_codes = res['code'].astype(str).str.strip().tolist()
        hist_data = get_technical_data_batch(valid_codes)
        
        if not hist_data.empty:
            # ... (後續的解析邏輯保持一致) ...
