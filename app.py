import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

# ==========================================
# 1. 介面與全域設定
# ==========================================
st.set_page_config(page_title="台股策略選股系統", layout="wide")
st.title("📈 台股策略選股系統 (基本面 + 技術面)")

# 基礎篩選條件設定
MIN_PRICE = 10
MAX_PRICE = 150
MIN_VOL_SHARES = 1000 * 1000  # 1000張 = 1,000,000股 (yfinance 成交量單位為股)
MIN_PE = 5
MAX_PE = 30
MIN_ROE = 5.0  # 5%

# ==========================================
# 2. KD 指標計算函數
# ==========================================
def calculate_kd(df, n=9):
    """計算 KD 指標"""
    df['Min_Low'] = df['Low'].rolling(window=n).min()
    df['Max_High'] = df['High'].rolling(window=n).max()
    
    # 計算 RSV
    df['RSV'] = 100 * (df['Close'] - df['Min_Low']) / (df['Max_High'] - df['Min_Low'])
    df['RSV'] = df['RSV'].fillna(50)  # 處理初期的 NaN

    # 計算 K 與 D (預設初始值為 50)
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
# 3. 股票資料抓取與分析核心
# ==========================================
@st.cache_data(ttl=3600)
def analyze_stock(tk):
    """抓取單檔股票的基本面與技術面，並判斷是否符合條件"""
    try:
        # 【關鍵修正】放棄有 Bug 的 yf.download，改用更穩定的 yf.Ticker().history()
        stock = yf.Ticker(tk)
        hist = stock.history(period="3mo")
        
        if hist.empty or len(hist) < 60:
            return None

        # 最新技術數據
        last_close = float(hist['Close'].iloc[-1])
        last_vol = float(hist['Volume'].iloc[-1])

        # 基本條件檢驗 1: 股價與成交量
        if not (MIN_PRICE <= last_close <= MAX_PRICE):
            return None
        if last_vol < MIN_VOL_SHARES:
            return None

        # 計算均線
        hist['MA5'] = hist['Close'].rolling(window=5).mean()
        hist['MA10'] = hist['Close'].rolling(window=10).mean()
        hist['MA20'] = hist['Close'].rolling(window=20).mean()
        hist['MA60'] = hist['Close'].rolling(window=60).mean()
        
        # 計算 KD
        hist = calculate_kd(hist)

        # 計算主力支撐 (Pivot Point Support 1)
        # 取近5日的最高與最低，搭配最新收盤價計算
        recent_high = float(hist['High'].iloc[-5:].max())
        recent_low = float(hist['Low'].iloc[-5:].min())
        pivot = (recent_high + recent_low + last_close) / 3
        support_1 = (2 * pivot) - recent_high

        # 取得最新與前一日資料
        latest = hist.iloc[-1]
        prev = hist.iloc[-2]

        # 判斷多頭排列 (5MA > 10MA > 20MA > 60MA)
        is_bull_market = (latest['MA5'] > latest['MA10'] > latest['MA20'] > latest['MA60'])
        
        # 判斷 KD 黃金交叉 (昨日 K<D，今日 K>D)
        kd_golden_cross = (prev['K'] < prev['D']) and (latest['K'] > latest['D'])

        # --- [B] 抓取基本面資料 ---
        # 為了加快速度，只有通過前述技術與價格量能條件的股票，才去查財報
        info = stock.info  # 這裡直接沿用前面建立好的 stock 物件，速度更快
        pe = info.get('trailingPE', 0)
        roe = info.get('returnOnEquity', 0)
        
        pe = float(pe) if pe is not None else 0.0
        roe = float(roe) * 100 if roe is not None else 0.0 # 轉換為百分比

        # 基本條件檢驗 2: PE 與 ROE
        if not (MIN_PE <= pe <= MAX_PE):
            return None
        if roe < MIN_ROE:
            return None

        # 回傳最終整理資料
        return {
            '股票代號': tk.replace('.TW', '').replace('.TWO', ''),
            '收盤價': round(last_close, 2),
            '成交張數': int(last_vol / 1000),
            '本益比(PE)': round(pe, 2),
            'ROE(%)': round(roe, 2),
            '主力支撐': round(support_1, 2),
            'K值': round(latest['K'], 2),
            'D值': round(latest['D'], 2),
            '多頭排列': '✅' if is_bull_market else '❌',
            'KD金叉': '✅' if kd_golden_cross else '❌'
        }

    except Exception as e:
        # 發生錯誤直接跳過該檔股票，避免卡死整個網頁
        print(f"Error processing {tk}: {e}")
        return None

# ==========================================
# 4. Streamlit 主程式介面
# ==========================================
st.markdown("### 🔍 策略執行條件")
st.markdown(f"""
- **基本條件**：股價 `{MIN_PRICE}~{MAX_PRICE}` 元、單日成交量大於 `{int(MIN_VOL_SHARES/1000)}` 張、本益比 `{MIN_PE}~{MAX_PE}`、ROE大於 `{MIN_ROE}%`。
- **技術條件**：計算多頭排列 (5MA>10MA>20MA>60MA)、KD黃金交叉。
""")

# 測試用股票清單
test_tickers = ['2330.TW', '2454.TW', '2317.TW', '2382.TW', '3231.TW', '2603.TW', '2356.TW', '2881.TW', '2882.TW']

if st.button('🚀 開始執行策略篩選'):
    progress_text = "正在掃描股票中，請稍候..."
    my_bar = st.progress(0, text=progress_text)
    
    results = []
    total_stocks = len(test_tickers)
    
    for i, ticker in enumerate(test_tickers):
        # 執行分析
        data = analyze_stock(ticker)
        if data:
            results.append(data)
            
        # 更新進度條
        percent_complete = (i + 1) / total_stocks
        my_bar.progress(percent_complete, text=f"掃描中... {ticker} ({i+1}/{total_stocks})")
        time.sleep(0.1) 
        
    my_bar.empty() # 清除進度條
    
    if results:
        st.success(f"掃描完成！共找到 {len(results)} 檔符合參數的股票。")
        df_results = pd.DataFrame(results)
        st.dataframe(df_results, use_container_width=True)
    else:
        st.warning("目前沒有符合所有篩選條件的股票。")
