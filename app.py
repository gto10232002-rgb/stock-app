import streamlit as st
import pandas as pd
import requests
import datetime
import time
import yfinance as yf

# ==========================================
# 1. 頁面配置
# ==========================================
st.set_page_config(page_title="StockTool", layout="wide")

st.markdown(
    "<style>"
    ".block-container {"
    "  padding-top: 3.6rem !important;"
    "}"
    "@media (max-width: 768px) {"
    "  .block-container {"
    "    padding-top: 4.6rem !important;"
    "  }"
    "}"
    "</style>",
    unsafe_allow_html=True
)

st.markdown("### 📊 台股多元策略選股系統")


# ==========================================
# 2. 基礎資料
# ==========================================
@st.cache_data(ttl=3600)
def get_stock_base_data_v3():
    try:
        url = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
        data = requests.get(url).json()
        df = pd.DataFrame(data)

        df = df[df["Code"].str.len() == 4]

        df["price"] = pd.to_numeric(df["ClosingPrice"].str.replace(",", ""), errors="coerce")
        df["vol"] = pd.to_numeric(df["TradeVolume"].str.replace(",", ""), errors="coerce") / 1000

        df = df.rename(columns={"Code": "code", "Name": "name"})

        return df
    except:
        return pd.DataFrame()


# ==========================================
# 技術指標
# ==========================================
@st.cache_data(ttl=600)
def get_single_stock_tech(code):
    try:
        hist = yf.download(f"{code}.TW", period="1mo", progress=False)

        if hist.empty or len(hist) < 2:
            return 0.0, 0.0

        high = hist["High"].max()
        cur = hist["Close"].iloc[-1]
        prev = hist["Close"].iloc[-2]

        dd = (high - cur) / high * 100 if high > 0 else 0
        chg = (cur - prev) / prev * 100 if prev > 0 else 0

        return round(dd, 2), round(chg, 2)
    except:
        return 0.0, 0.0


# ==========================================
# 主程式
# ==========================================
df = get_stock_base_data_v3()

if df.empty:
    st.warning("資料取得失敗")
    st.stop()


# Sidebar（✅ 保留你原本操作模式）
st.sidebar.header("🎯 基礎條件")

min_p = st.sidebar.number_input("最低股價", value=0.0)
max_p = st.sidebar.number_input("最高股價", value=500.0)
min_v = st.sidebar.number_input("最低成交量", value=1000)

st.sidebar.header("🧠 策略")

enable_drawdown = st.sidebar.checkbox("回檔策略", value=False)
enable_strong = st.sidebar.checkbox("強勢族群", value=False)
min_dd = st.sidebar.slider("最低回檔%", 0, 50, 5)
min_chg = st.sidebar.slider("最低漲幅%", -10, 10, 5)


# ✅ 基礎篩選（已修正符號）
res = df[
    (df["price"] >= min_p)
    & (df["price"] <= max_p)
    & (df["vol"] >= min_v)
].copy()

if res.empty:
    st.warning("無符合條件")
    st.stop()


# ✅ 技術分析
st.info(f"分析 {len(res)} 檔股票")

drawdown_map = {}
change_map = {}

progress = st.progress(0)

for i, code in enumerate(res["code"]):
    dd, chg = get_single_stock_tech(code)
    drawdown_map[code] = dd
    change_map[code] = chg
    progress.progress((i + 1) / len(res))
    time.sleep(0.01)

progress.empty()

res["回檔%"] = res["code"].map(drawdown_map)
res["今日漲幅%"] = res["code"].map(change_map)


# ==========================================
# 策略（✅ 完整保留）
# ==========================================
if enable_drawdown:
    res = res[res["回檔%"] >= min_dd]

if enable_strong:
    res = res[res["今日漲幅%"] >= min_chg]


# 排序
res = res.sort_values(by=["今日漲幅%", "回檔%"], ascending=[False, False])


# ==========================================
# 顯示
# ==========================================
st.success(f"結果：{len(res)} 檔")

st.dataframe(
    res[["code", "name", "price", "vol", "今日漲幅%", "回檔%"]],
    use_container_width=True,
    height=600
)
