import streamlit as st
import pandas as pd
import requests
import urllib3

# 1. 網頁基本外觀排版設定
st.set_page_config(page_title="台股即時選股儀表板", layout="wide")
st.title("📈 台股全市場即時篩選與策略系統")

# 2. 自動關閉 SSL 安全憑證警告（解決台灣政府/證交所網站常見的連線異常問題）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 3. 建立具備防阻擋與快取機制的資料抓取函式
@st.cache_data(ttl=300)  # 資料快取 5 分鐘，避免頻繁抓取被證交所封鎖
def fetch_stock_data():
    url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    
    # 完整瀏覽器偽裝標頭
    hd = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    try:
        # 發送請求，設定超時與忽略憑證驗證
        res_p = requests.get(url, headers=hd, timeout=15, verify=False)
        
        if res_p.status_code == 200:
            data_json = res_p.json()
            if data_json:
                df = pd.DataFrame(data_json)
                
                # 強制將文字型態的數據清除逗號並轉為數字，防止滑桿邏輯崩潰
                numeric_cols = ['OpeningPrice', 'HighestPrice', 'LowestPrice', 'ClosingPrice', 'TradeVolume', 'TradeValue']
                for col in numeric_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce')
                
                # 【雙向相容設計】同時產生中文與英文欄位名稱，確保任何策略皆可讀取
                mapping = {
                    'Code': '證券代號', 'Name': '證券名稱', 'OpeningPrice': '開盤價',
                    'HighestPrice': '最高價', 'LowestPrice': '最低價', 'ClosingPrice': '收盤價',
                    'TradeVolume': '成交股數', 'TradeValue': '成交金額', 'Change': '漲跌價差',
                    'Transaction': '成交筆數'
                }
                for eng, chn in mapping.items():
                    if eng in df.columns:
                        df[chn] = df[eng]
                        
                return df, None
        return pd.DataFrame(), f"HTTP 錯誤碼: {res_p.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

# 4. 執行資料載入
df_price, error_msg = fetch_stock_data()

# 5. 畫面呈現與異常診斷
if error_msg:
    st.error(f"❌ 股價API連線異常 (詳細原因: {error_msg})")
    st.info("💡 提示：若持續出現此錯誤，代表您目前的網路環境（或雲端平台）被證交所伺服器嚴格阻擋，建議您可以嘗試更換網路環境、或稍後重新整理網頁。")
elif df_price.empty:
    st.warning("⚠️ 已成功連線，但證交所目前未回傳任何股票資料。")
else:
    # 側邊欄篩選器介面
    st.sidebar.header("🔍 策略條件設定")
    
    # 動態取得全市場最高股價，作為滑桿上限
    valid_prices = df_price['收盤價'].dropna()
    max_market_price = float(valid_prices.max()) if not valid_prices.empty else 1000.0
    
    # 數值設定為 50.0，且 step 精準設定為 1.0，澈底排除先前 step 的小數點衝突問題
    price_cutoff = st.sidebar.slider(
        "最低收盤價門檻 (元)",
        min_value=0.0,
        max_value=max_market_price,
        value=50.0,  # 預設為您指定的 50
        step=1.0,    # 整數步進，絕對不報錯
        help="只顯示收盤價高於此數值的股票"
    )
    
    # 成交量篩選（以張數為單位，1張 = 1,000股）
    volume_cutoff_k = st.sidebar.slider(
        "最低成交量 (張)",
        min_value=0,
        max_value=5000,
        value=100,
        step=50
    )
    volume_shares = volume_cutoff_k * 1000

    # 6. 核心選股策略篩選
    filtered_df = df_price[
        (df_price['收盤價'] >= price_cutoff) & 
        (df_price['成交股數'] >= volume_shares)
    ]

    # 7. 數據儀表板視覺化呈現
    m1, m2 = st.columns(2)
    with m1:
        st.metric("當前市場總觀測股票數", f"{len(df_price)} 檔")
    with m2:
        st.metric("符合您策略的股票數", f"{len(filtered_df)} 檔")

    st.subheader("📊 策略篩選結果列表")
    
    # 挑選要呈現在網頁上的乾淨欄位
    display_cols = ['證券代號', '證券名稱', '開盤價', '最高價', '最低價', '收盤價', '成交股數']
    available_cols = [c for c in display_cols if c in filtered_df.columns]
    
    if not filtered_df.empty:
        # 呈現表格並自動放大至視窗寬度
        st.dataframe(
            filtered_df[available_cols].reset_index(drop=True), 
            use_container_width=True
        )
    else:
        st.info("💡 目前沒有股票符合此篩選條件，請嘗試調低側邊欄的股價或成交量門檻。")
