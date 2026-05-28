import streamlit as st
import pandas as pd
import requests
import datetime
import time
import yfinance as yf

# ... [前面的 get_stock_base_data 保持不變，略過以節省篇幅] ...

# 🛠️ 終極修復：完全不依賴 MultiIndex 或欄位名稱，直接暴力解鎖
def get_technical_data_force(valid_codes):
    ticker_list = [f"{c}.TW" for c in valid_codes]
    # 一次性下載，我們只取 Close 和 High
    try:
        data = yf.download(ticker_list, period="1mo", threads=True, progress=False)
        return data
    except Exception:
        return pd.DataFrame()

# 在主程式中修改這段解析：
if not res.empty and (enable_drawdown or enable_strong):
    with st.spinner("正在分析技術指標..."):
        valid_codes = res['code'].astype(str).str.strip().tolist()
        hist = get_technical_data_force(valid_codes)
        
        # 建立空的字典準備存數據
        dd_dict = {}
        chg_dict = {}

        if not hist.empty:
            # 遍歷每一個代號
            for code in valid_codes:
                ticker = f"{code}.TW"
                try:
                    # 強制提取資料，不論它現在是什麼格式
                    # 如果是 MultiIndex，我們嘗試用 (指標, ticker) 提取
                    if 'Close' in hist.columns.names or isinstance(hist.columns, pd.MultiIndex):
                        close_s = hist.xs(ticker, level=1, axis=1)['Close'] if ticker in hist.columns.levels[1] else None
                        high_s = hist.xs(ticker, level=1, axis=1)['High'] if ticker in hist.columns.levels[1] else None
                    else:
                        # 如果是單層欄位
                        close_s = hist[[c for c in hist.columns if 'Close' in c and code in c]].iloc[:, 0]
                        high_s = hist[[c for c in hist.columns if 'High' in c and code in c]].iloc[:, 0]
                    
                    if close_s is not None and high_s is not None:
                        close_s = close_s.ffill().dropna()
                        high_s = high_s.ffill().dropna()
                        if len(close_s) >= 2:
                            max_h = high_s.max()
                            last_c = close_s.iloc[-1]
                            prev_c = close_s.iloc[-2]
                            dd_dict[code] = round(((max_h - last_c) / max_h * 100), 2)
                            chg_dict[code] = round(((last_c - prev_c) / prev_c * 100), 2)
                except:
                    continue
        
        res['回檔%'] = res['code'].astype(str).map(dd_dict).fillna(0.0)
        res['今日漲幅%'] = res['code'].astype(str).map(chg_dict).fillna(0.0)

# ... [後續排序與顯示邏輯保持不變] ...
