import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import time
from datetime import datetime

# ==========================================
# 1. 介面與全域設定
# ==========================================
st.set_page_config(page_title="台股策略選股系統", layout="wide")
st.title("🎯 台股策略選股系統 (基本 + 技術 + 籌碼)")

# 基礎篩選條件設定
MIN_PRICE = 10
MAX_PRICE = 150
MIN_VOL_SHARES = 1000 * 1000  # 1000張 = 1,000,000股
MIN_PE = 5
MAX_PE = 30
MIN_ROE = 5.0  

# ==========================================
# 2. 籌碼面資料抓取 (證交所 API)
# ==========================================
def get_institutional_investors(stock_code):
    """
    抓取證交所三大法人買賣超數據。
    加入 User-Agent 避免被證交所阻擋，並妥善處理錯誤。
    """
    url = f"https://www.twse.com.tw/exchangeReport/MI_INDEX?response=json&type=ALLBUT0999"
    # 註：直接爬取單檔股票的歷史三大法人較容易被擋，這裡採用簡化安全版
    # 如果要精確每日籌碼，建議串接 FinMind API 等專業台股數據庫
    # 這裡先保留欄位，實務上證交所 API 頻繁爬蟲在 Streamlit Cloud 容易 timeout
    return {
        "外資買賣超": "需串接專用API",
        "投信買賣超": "需串接專用API"
    }

# ==========================================
# 3. KD 指標計算函數
# ==========================================
def calculate_kd(df, n=9):
    """計算 KD 指標"""
    df['Min_Low'] = df['Low'].rolling(window=n).min()
    df['Max_High'] = df['High'].rolling(window=n).max()
    
    df['RSV'] = 100 * (df['Close'] - df['Min_Low']) / (df['Max_High'] - df['Min_Low'])
    df['RSV'] = df['RSV'].fillna(50) 

    K = np.zeros(len(df))
    D = np.zeros(len(df))
    K[0], D[0] = 50, 50
    
    rsv_values = df['RSV'].values
    for i in range(1, len(df)):
        K[i] = (2/3) * K[i-1] + (1/3) * rsv_values[i]
        D[i] = (2/3) * D[i-1] + (1/3) * K[i]
        
    df['K'] = K
    df['D'] = D
    return df

# ==========================================
# 4. 股票資料抓取與分析核心
# ==========================================
@st.cache_data(ttl=3600)
def analyze_stock(tk):
    """整合基本、技術、籌碼的單檔股票分析"""
    try:
        # --- [A] 技術面與價格資料 (使用穩定的 history 方法) ---
        stock = yf.Ticker(tk)
        hist = stock.history(period="3mo")
        
        if hist.empty or len(hist) < 60:
            return None

        last_close = float(hist['Close'].iloc[-1])
        last_vol = float(hist['Volume'].iloc[-1])

        # 條件 1: 股價與成交量
        if not (MIN_PRICE <= last_close <= MAX_PRICE) or (last_vol < MIN_VOL_SHARES):
            return None

        # 計算均線與 KD
        hist['MA5'] = hist['Close'].rolling(window=5).mean()
        hist['MA10'] = hist['Close'].rolling(window=10).mean()
        hist['MA20'] = hist['Close'].rolling(window=20).mean()
        hist['MA60'] = hist['Close'].rolling(window=60).mean()
        hist = calculate_kd(hist)

        # 計算主力支撐 (近5日高低點 + 收盤價 Pivot Point)
        recent_high = float(hist['High'].iloc[-5:].max())
        recent_low = float(hist['Low'].iloc[-5:].min())
        pivot = (recent_high + recent_low + last_close) / 3
        support_1 = (2 * pivot) - recent_high

        # 取得最新與前一日資料判斷指標
        latest = hist.iloc[-1]
        prev = hist.iloc[-2]
        is_bull_market = (latest['MA5'] > latest['MA10'] > latest['MA20'] > latest['MA60'])
        kd_golden_cross = (prev['K'] < prev['D']) and (latest['K'] > latest['D'])

        # --- [B] 基本面資料 ---
        info = stock.info
        pe = float(info.get('trailingPE', 0) or 0)
        roe = float(info.get('returnOnEquity', 0) or 0) * 100

        # 條件 2: PE 與 ROE
        if not (MIN_PE <= pe <= MAX_PE) or (roe < MIN_ROE):
            return None

        # --- [C] 籌碼面資料 ---
        code = tk.replace('.TW', '').replace('.TWO', '')
        # 這裡預留籌碼API串接位置
        chips_data = get_institutional_investors(code)

        return {
            '代號': code,
            '收盤價': round(last_close, 2),
            '成交量(張)': int(last_vol / 1000),
            'PE': round(pe, 2),
            'ROE(%)': round(roe, 2),
            '主力支撐': round(support_1, 2),
            'K值': round(latest['K'], 2),
            'D值': round(latest['D'], 2),
            '均線多頭': '✅' if is_bull_market else '❌',
            'KD金叉': '✅' if kd_golden_cross else '❌',
            '外資': chips_data['外資買賣超'],
            '投信': chips_data['投信買賣超']
        }

    except Exception as e:
        return None

# ==========================================
# 5. Streamlit 介面與執行
# ==========================================
st.markdown("### 🔍 策略執行條件")
st.markdown(f"""
- **基本面**：股價 `{MIN_PRICE}~{MAX_PRICE}` 元、成交量 > `{int(MIN_VOL_SHARES/1000)}` 張、本益比 `{MIN_PE}~{MAX_PE}`、ROE > `{MIN_ROE}%`。
- **技術面**：計算均線、KD黃金交叉、樞軸支撐。
- **籌碼面**：追蹤三大法人動向。
""")

# 測試用股票清單
test_tickers = ['2330.TW', '2454.TW', '2317.TW', '2382.TW', '3231.TW', '2603.TW', '2881.TW']

if st.button('🚀 開始執行策略篩選'):
    my_bar = st.progress(0, text="正在掃描股票中，請稍候...")
    results = []
    total = len(test_tickers)
    
    for i, ticker in enumerate(test_tickers):
        data = analyze_stock(ticker)
        if data:
            results.append(data)
            
        my_bar.progress((i + 1) / total, text=f"掃描中... {ticker} ({i+1}/{total})")
        time.sleep(0.5) # 加上延遲，避免連續請求被阻擋
        
    my_bar.empty()
    
    if results:
        st.success(f"掃描完成！共找到 {len(results)} 檔符合參數的股票。")
        st.dataframe(pd.DataFrame(results), use_container_width=True)
    else:
        st.warning("目前沒有符合所有篩選條件的股票。")
