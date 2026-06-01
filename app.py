import streamlit as st
import pandas as pd
import numpy as np
import requests
import datetime as dt
import yfinance as yf

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed


# ==========================================
# 0. 頁面設定 / 手機友善 CSS
# ==========================================
st.set_page_config(
    page_title="StockTool",
    layout="wide",
)

st.markdown(
    "<style>"
    ".block-container {"
    "    padding-top: 1.0rem !important;"
    "    padding-bottom: 1rem !important;"
    "    padding-left: 0.8rem !important;"
    "    padding-right: 0.8rem !important;"
    "    max-width: 1200px;"
    "}"
    "h1, h2, h3 {"
    "    margin-top: 0rem !important;"
    "    margin-bottom: 0.4rem !important;"
    "}"
    ".mobile-card {"
    "    border: 1px solid rgba(180,180,180,0.25);"
    "    border-radius: 14px;"
    "    padding: 14px 14px 10px 14px;"
    "    margin-bottom: 10px;"
    "    background: rgba(255,255,255,0.02);"
    "}"
    ".mobile-title {"
    "    font-size: 1.05rem;"
    "    font-weight: 700;"
    "    margin-bottom: 0.25rem;"
    "    line-height: 1.35;"
    "}"
    ".mobile-sub {"
    "    font-size: 0.86rem;"
    "    color: #888;"
    "    margin-bottom: 0.45rem;"
    "}"
    ".mobile-row {"
    "    font-size: 0.92rem;"
    "    line-height: 1.6;"
    "}"
    ".tag-strong {"
    "    color: #d97706;"
    "    font-weight: 700;"
    "}"
    ".tag-good {"
    "    color: #059669;"
    "    font-weight: 700;"
    "}"
    ".tag-watch {"
    "    color: #64748b;"
    "    font-weight: 700;"
    "}"
    "@media (max-width: 768px) {"
    "    .block-container {"
    "        padding-top: 0.8rem !important;"
    "        padding-left: 0.6rem !important;"
    "        padding-right: 0.6rem !important;"
    "    }"
    "}"
    "</style>",
    unsafe_allow_html=True
)

st.markdown("## 📊 台股多元策略選股系統")
st.caption("手機優先版｜先設定條件，再按「開始分析」")


# ==========================================
# 1. 常數設定
# ==========================================
IND_MAP = {
    "01": "水泥工業", "02": "食品工業", "03": "塑膠工業", "04": "紡織纖維",
    "05": "電機機械", "06": "電器電纜", "07": "化學工業", "08": "生技醫療業",
    "09": "玻璃陶瓷", "10": "造紙工業", "11": "鋼鐵工業", "12": "橡膠工業",
    "13": "汽車工業", "14": "建材營建", "15": "航運業", "16": "觀光餐旅",
    "17": "金融保險", "18": "貿易百貨", "19": "綜合業", "20": "其他業",
    "21": "化學工業", "22": "生技醫療業", "23": "油電燃氣業", "24": "半導體業",
    "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業", "28": "電子零組件業",
    "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業", "35": "綠能環保",
    "36": "數位雲端", "37": "運動休閒", "38": "居家生活", "91": "存託憑證"
}

ETF_DB = {
    "2330": ["0050", "00919", "00929"], "2317": ["0050", "00919", "00929"],
    "2454": ["0050", "0056", "00878", "00919", "00929", "00940"], "2308": ["0050", "00929"],
    "3711": ["0050", "0056", "00878", "00919"], "2303": ["0050", "0056", "00878", "00919", "00929", "00940"],
    "2881": ["0050", "00878", "00919", "00940"], "2882": ["0050", "00878", "00919"],
    "2891": ["0050", "0056", "00878", "00919", "00940"], "2382": ["0050", "0056", "00878", "00919", "00940"],
    "2886": ["0050", "00878"], "3008": ["0050", "00919", "00929"], "2884": ["0050"],
    "2885": ["0050", "00878", "00940"], "2892": ["0050", "00940"],
    "2357": ["0050", "0056", "00878", "00919", "00929", "00940"], "3231": ["0050", "0056", "00878", "00929"],
    "1216": ["0050", "0056", "00878", "00940"], "2412": ["0050", "00878"], "1301": ["0050"],
    "1303": ["0050"], "2603": ["0050", "0056", "00878", "00919", "00940"], "3037": ["0050"],
    "2301": ["0050", "0056", "00878", "00929"], "4904": ["0050", "00878"], "2327": ["0050", "00919"],
    "3045": ["0050", "00878", "00940"], "2408": ["0050"], "2449": ["0050", "0056", "00878"],
    "2345": ["0050"], "2395": ["0050"], "2360": ["0050"], "2368": ["0050"], "3017": ["0050"],
    "2383": ["0050"], "2207": ["0050"], "6669": ["0050"], "3653": ["0050"], "3661": ["0050"],
    "2002": ["0050"], "5880": ["0050"], "2880": ["0050", "0056", "00878"], "2883": ["0050", "00940"],
    "2890": ["0050", "00940"], "6505": ["0050"], "6919": ["0050"], "7769": ["0050"],
    "2059": ["0050"], "2344": ["0050"], "2376": ["0056", "00878"],
    "2324": ["0056", "00878", "00919", "00929", "00940"],
    "2356": ["0056", "00878", "00940"], "2385": ["0056", "00940"],
    "3034": ["0056", "00878", "00919", "00929", "00940"], "3702": ["0056", "00940"],
    "4938": ["0056", "00929", "00940"], "3293": ["0056", "00878", "00940"],
    "2474": ["0056", "00878", "00940"], "3005": ["0056", "00940"], "2379": ["0056", "00878", "00940"],
    "2404": ["0056", "00919", "00929", "00940"], "6121": ["0056"],
    "2618": ["0056", "00878", "00919", "00940"], "5347": ["0056", "00878", "00919"],
    "3044": ["0056", "00929", "00940"], "2610": ["0056", "00940"], "3036": ["0056", "00929", "00940"],
    "1504": ["0056", "00940"], "2312": ["0056", "00940"], "2458": ["0056", "00940"],
    "3042": ["0056", "00940"], "5469": ["0056", "00940"], "6278": ["0056", "00940"],
    "2915": ["0056", "00940"], "8069": ["0056", "00940"], "3023": ["0056", "00940"],
    "2421": ["0056", "00940"], "6414": ["0056", "00940"], "3406": ["0056", "00919", "00940"],
    "2439": ["0056", "00940"], "6188": ["0056", "00940"], "6285": ["0056", "00940"],
    "8016": ["0056", "00940"], "6139": ["0056", "00940"], "5269": ["0056", "00940"],
    "6196": ["0056", "00940"], "6239": ["0056", "00919", "00929", "00940"], "4958": ["00878", "00919"],
    "1402": ["00878"], "2912": ["00878", "00940"], "2609": ["00919"], "8209": ["00919"],
    "6488": ["00929", "00940"], "2801": ["00940"], "9904": ["00940"], "1102": ["00940"],
    "4915": ["00940"], "2615": ["00940"], "1319": ["00940"], "3706": ["00940"],
    "6176": ["00940"], "1513": ["00940"], "2393": ["00940"], "6257": ["00940"]
}

BASE_CACHE_TTL = 3600
TECH_CACHE_TTL = 900
YF_CHUNK_SIZE = 30
MAX_ANALYZE_DEFAULT = 120
T86_LOOKBACK_DAYS = 7


# ==========================================
# 2. HTTP 工具函式
# ==========================================
@st.cache_resource
def get_http_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    return session


def safe_to_numeric(series):
    return pd.to_numeric(
        series.astype(str).str.replace(",", "", regex=False),
        errors="coerce"
    )


def fetch_json(session, url, timeout=20):
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.json(), None
    except Exception as e:
        return None, str(e)


# ==========================================
# 3. 基礎資料清洗函式
# ==========================================
def build_price_df(raw):
    if not isinstance(raw, list) or not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    need_cols = {"Code", "ClosingPrice", "TradeVolume", "TradeValue", "Name"}
    if not need_cols.issubset(df.columns):
        return pd.DataFrame()

    df = df[df["Code"].astype(str).str.len() == 4].copy()
    df["price"] = safe_to_numeric(df["ClosingPrice"])
    df["vol"] = safe_to_numeric(df["TradeVolume"]) / 1000
    df["trade_value"] = safe_to_numeric(df["TradeValue"])

    df = df[["Code", "Name", "price", "vol", "trade_value"]].rename(
        columns={"Code": "code", "Name": "name"}
    )
    return df


def build_pe_df(raw):
    if not isinstance(raw, list) or not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    if not {"Code", "PEratio"}.issubset(df.columns):
        return pd.DataFrame()

    df = df[["Code", "PEratio"]].rename(columns={"Code": "code", "PEratio": "pe"})
    df["pe"] = safe_to_numeric(df["pe"])
    return df


def build_industry_df(raw):
    if not isinstance(raw, list) or not raw:
        return pd.DataFrame()

    df = pd.DataFrame(raw)
    if not {"公司代號", "產業別"}.issubset(df.columns):
        return pd.DataFrame()

    df = df[["公司代號", "產業別"]].rename(columns={"公司代號": "code", "產業別": "industry"})
    df["industry"] = df["industry"].astype(str).str.strip().map(IND_MAP).fillna(df["industry"])
    df["industry"] = df["industry"].replace(["", "nan", "None"], "其他").fillna("其他")
    return df


def fetch_chip_df(session, lookback_days=7):
    warnings = []

    for i in range(lookback_days):
        date_str = (dt.datetime.now() - dt.timedelta(days=i)).strftime("%Y%m%d")
        url = "https://www.twse.com.tw/rwd/zh/fund/T86?date={}&selectType=ALLBUT0999&response=json".format(date_str)

        data, err = fetch_json(session, url)
        if err or not isinstance(data, dict):
            continue

        if "data" not in data or "fields" not in data:
            continue

        raw_data = data["data"]
        fields = data["fields"]
        if not raw_data or not fields:
            continue

        df_raw = pd.DataFrame(raw_data, columns=fields)
        df_raw.columns = df_raw.columns.str.strip()

        fi_cols = [c for c in df_raw.columns if "外資" in c and "買賣超" in c]
        it_cols = [c for c in df_raw.columns if "投信" in c and "買賣超" in c]

        if not fi_cols or not it_cols or "證券代號" not in df_raw.columns:
            continue

        fi_col = fi_cols[0]
        it_col = it_cols[0]

        df = pd.DataFrame({
            "code": df_raw["證券代號"].astype(str).str.strip(),
            "fi": safe_to_numeric(df_raw[fi_col]) / 1000,
            "it": safe_to_numeric(df_raw[it_col]) / 1000
        })
        return df, warnings

    warnings.append("⚠️ 無法取得近 7 日籌碼資料，可能為非交易日、盤後尚未更新或 API 壅塞。")
    return pd.DataFrame(), warnings


# ==========================================
# 4. 基礎資料主函式（快取）
# ==========================================
@st.cache_data(ttl=BASE_CACHE_TTL, show_spinner=False)
def get_stock_base_data_v4():
    session = get_http_session()
    warnings = []
    errors = []

    urls = {
        "price": "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL",
        "pe": "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL",
        "industry": "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
    }

    results = {}

    with ThreadPoolExecutor(max_workers=3) as ex:
        future_map = {ex.submit(fetch_json, session, url): key for key, url in urls.items()}
        for future in as_completed(future_map):
            key = future_map[future]
            try:
                raw, err = future.result()
                results[key] = (raw, err)
            except Exception as e:
                results[key] = (None, str(e))

    price_raw, price_err = results.get("price", (None, "股價 API 失敗"))
    pe_raw, pe_err = results.get("pe", (None, None))
    ind_raw, ind_err = results.get("industry", (None, None))

    if price_err:
        errors.append("❌ 每日股價資料失敗：{}".format(price_err))
    if pe_err:
        warnings.append("⚠️ 本益比資料失敗：{}".format(pe_err))
    if ind_err:
        warnings.append("⚠️ 產業資料失敗：{}".format(ind_err))

    df_price = build_price_df(price_raw)
    df_pe = build_pe_df(pe_raw) if pe_raw is not None else pd.DataFrame()
    df_ind = build_industry_df(ind_raw) if ind_raw is not None else pd.DataFrame()
    df_chips, chip_warnings = fetch_chip_df(session, lookback_days=T86_LOOKBACK_DAYS)
    warnings.extend(chip_warnings)

    if df_price.empty:
        errors.append("❌ 股價主資料為空，無法建立主表。")
        return pd.DataFrame(), warnings, errors

    if df_chips.empty:
        errors.append("❌ 籌碼資料為空，無法完成集中度計算。")
        return pd.DataFrame(), warnings, errors

    df = df_price.merge(df_chips, on="code", how="inner")

    if not df_pe.empty:
        df = df.merge(df_pe, on="code", how="left")
    else:
        df["pe"] = np.nan

    if not df_ind.empty:
        df = df.merge(df_ind, on="code", how="left")
    else:
        df["industry"] = "其他"

    df["industry"] = df["industry"].fillna("其他")
    df["chip_ratio"] = np.where(df["vol"] > 0, ((df["fi"] + df["it"]) / df["vol"] * 100), np.nan).round(2)
    df["value_billion"] = (df["trade_value"] / 100000000).round(2)

    float_cols = ["price", "vol", "trade_value", "fi", "it", "pe", "chip_ratio", "value_billion"]
    for c in float_cols:
        if c in df.columns:
            df[c] = df[c].astype("float32")

    return df, warnings, errors


# ==========================================
# 5. 單檔技術指標（保險 fallback）
# ==========================================
@st.cache_data(ttl=TECH_CACHE_TTL, show_spinner=False)
def get_single_stock_tech(code):
    tk = "{}.TW".format(str(code).strip())
    dd, chg = 0.0, 0.0

    try:
        hist = yf.download(
            tickers=tk,
            period="1mo",
            interval="1d",
            auto_adjust=False,
            progress=False,
            threads=False
        )

        if hist is None or hist.empty or len(hist) < 2:
            return dd, chg

        closes = hist["Close"].dropna()
        highs = hist["High"].dropna()

        if len(closes) >= 2 and len(highs) >= 1:
            current = float(closes.iloc[-1])
            prev_close = float(closes.iloc[-2])
            high_1m = float(highs.max())

            if high_1m > 0:
                dd = round(((high_1m - current) / high_1m) * 100, 2)
            if prev_close > 0:
                chg = round(((current - prev_close) / prev_close) * 100, 2)
    except Exception:
        pass

    return dd, chg


# ==========================================
# 6. 批次技術指標（加速核心）
# ==========================================
@st.cache_data(ttl=TECH_CACHE_TTL, show_spinner=False)
def get_multi_stock_tech(codes, chunk_size=30):
    if not codes:
        return pd.DataFrame(columns=["code", "回檔%", "今日漲幅%"])

    all_rows = []
    tickers = ["{}.TW".format(str(code).strip()) for code in codes]

    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]

        try:
            hist = yf.download(
                tickers=chunk,
                period="1mo",
                interval="1d",
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True
            )
        except Exception:
            hist = None

        if hist is None or hist.empty:
            for tk in chunk:
                code = tk.replace(".TW", "")
                dd, chg = get_single_stock_tech(code)
                all_rows.append({
                    "code": code,
                    "回檔%": dd,
                    "今日漲幅%": chg
                })
            continue

        is_multi = isinstance(hist.columns, pd.MultiIndex)

        for tk in chunk:
            code = tk.replace(".TW", "")

            try:
                if is_multi:
                    if tk not in hist.columns.get_level_values(0):
                        dd, chg = get_single_stock_tech(code)
                        all_rows.append({
                            "code": code,
                            "回檔%": dd,
                            "今日漲幅%": chg
                        })
                        continue
                    sub = hist[tk].dropna(how="all")
                else:
                    sub = hist.dropna(how="all")

                if sub.empty or len(sub) < 2:
                    dd, chg = get_single_stock_tech(code)
                    all_rows.append({
                        "code": code,
                        "回檔%": dd,
                        "今日漲幅%": chg
                    })
                    continue

                closes = sub["Close"].dropna()
                highs = sub["High"].dropna()

                if len(closes) < 2 or highs.empty:
                    dd, chg = get_single_stock_tech(code)
                    all_rows.append({
                        "code": code,
                        "回檔%": dd,
                        "今日漲幅%": chg
                    })
                    continue

                current = float(closes.iloc[-1])
                prev_close = float(closes.iloc[-2])
                high_1m = float(highs.max())

                dd = round(((high_1m - current) / high_1m) * 100, 2) if high_1m > 0 else 0.0
                chg = round(((current - prev_close) / prev_close) * 100, 2) if prev_close > 0 else 0.0

                all_rows.append({
                    "code": code,
                    "回檔%": dd,
                    "今日漲幅%": chg
                })

            except Exception:
                dd, chg = get_single_stock_tech(code)
                all_rows.append({
                    "code": code,
                    "回檔%": dd,
                    "今日漲幅%": chg
                })

    df = pd.DataFrame(all_rows)
    if df.empty:
        return pd.DataFrame(columns=["code", "回檔%", "今日漲幅%"])

    return df.drop_duplicates(subset=["code"], keep="last")


# ==========================================
# 7. 篩選與策略函式
# ==========================================
def apply_base_filters(df, min_p, max_p, min_v, max_pe, target_industry):
    res = df[(df["price"] >= min_p) & (df["price"] <= max_p) & (df["vol"] >= min_v)].copy()

    if max_pe > 0:
        pe_mask = ((res["pe"] > 0) & (res["pe"] <= max_pe)).fillna(False)
        res = res[pe_mask]

    if target_industry != "全部":
        res = res[(res["industry"] == target_industry).fillna(False)]

    return res


def apply_strategy_filters(
    res,
    enable_drawdown,
    enable_strong,
    dynamic_threshold,
    support_mode,
    min_dd,
    min_change
):
    if res.empty:
        return res

    mask_drawdown = pd.Series(False, index=res.index)
    mask_strong = pd.Series(False, index=res.index)

    if enable_drawdown:
        sub_mask = pd.Series(True, index=res.index)

        if dynamic_threshold:
            cond_large = (res["value_billion"] >= 5.0) & (res["chip_ratio"] >= 2.5)
            cond_small = (res["value_billion"] < 5.0) & (res["chip_ratio"] >= 5.0)
            sub_mask = sub_mask & (cond_large | cond_small)

        if support_mode == "單日爆發強勢型":
            sub_mask = sub_mask & (res["chip_ratio"] >= 5.0)

        sub_mask = sub_mask & (res["回檔%"] >= min_dd)

        if support_mode == "波段洗刷接貨型":
            sub_mask = sub_mask & (res["回檔%"] >= max(8.0, float(min_dd)))

        mask_drawdown = sub_mask

    if enable_strong:
        mask_strong = (res["今日漲幅%"] >= min_change)

    if enable_drawdown and enable_strong:
        return res[mask_drawdown | mask_strong]
    elif enable_drawdown:
        return res[mask_drawdown]
    elif enable_strong:
        return res[mask_strong]
    else:
        return res


def add_support_strength(res):
    if res.empty:
        res["支撐力道"] = pd.Series(dtype="object")
        return res

    conditions = [
        res["chip_ratio"] >= 10.0,
        res["chip_ratio"] >= 5.0
    ]
    choices = ["🔥 極強支撐", "✅ 健康買盤"]
    res["支撐力道"] = np.select(conditions, choices, default="🔹 觀察中")
    return res


def add_etf_info(res):
    if res.empty:
        return res

    def merge_etf_text(code, name):
        c = str(code).strip()
        n = str(name).strip()
        if c in ETF_DB:
            return "{} ({})".format(n, ",".join(ETF_DB[c]))
        return n

    res["name"] = [merge_etf_text(code, name) for code, name in zip(res["code"], res["name"])]
    return res


def sort_result(res, enable_strong, enable_drawdown):
    if res.empty:
        return res

    if enable_strong and not enable_drawdown:
        return res.sort_values(by="今日漲幅%", ascending=False)

    return res.sort_values(by=["chip_ratio", "回檔%"], ascending=[False, False])


def build_display_df(res):
    if res.empty:
        return res

    res["K線連結"] = res["code"].astype(str).apply(lambda x: "https://tw.stock.yahoo.com/quote/{}".format(x))

    display_df = res.rename(columns={
        "code": "代號",
        "name": "名稱",
        "industry": "產業",
        "price": "股價",
        "chip_ratio": "集中度",
        "pe": "本益比",
        "value_billion": "成交額"
    })
    return display_df


# ==========================================
# 8. 手機卡片渲染
# ==========================================
def support_class(text):
    if "極強" in text:
        return "tag-strong"
    elif "健康" in text:
        return "tag-good"
    return "tag-watch"


def format_pe_value(val):
    if pd.isna(val):
        return "N/A"
    try:
        return "{:.2f}".format(float(val))
    except Exception:
        return str(val)


def render_mobile_cards(df_cards):
    if df_cards.empty:
        st.info("目前沒有符合條件的股票。")
        return

    for _, row in df_cards.iterrows():
        cls = support_class(str(row["支撐力道"]))
        html = (
            '<div class="mobile-card">'
            '<div class="mobile-title">{} {}</div>'
            '<div class="mobile-sub">{}</div>'
            '<div class="mobile-row">'
            '股價 <b>{:.2f}</b> ｜ 漲幅 <b>{:.2f}%</b><br>'
            '回檔 <b>{:.2f}%</b> ｜ 集中度 <b>{:.2f}%</b><br>'
            '成交額 <b>{:.2f} 億</b> ｜ 本益比 <b>{}</b><br>'
            '支撐：<span class="{}">{}</span>'
            '</div>'
            '</div>'
        ).format(
            str(row["代號"]),
            str(row["名稱"]),
            str(row["產業"]),
            float(row["股價"]) if pd.notna(row["股價"]) else 0.0,
            float(row["今日漲幅%"]) if pd.notna(row["今日漲幅%"]) else 0.0,
            float(row["回檔%"]) if pd.notna(row["回檔%"]) else 0.0,
            float(row["集中度"]) if pd.notna(row["集中度"]) else 0.0,
            float(row["成交額"]) if pd.notna(row["成交額"]) else 0.0,
            format_pe_value(row["本益比"]),
            cls,
            str(row["支撐力道"])
        )
        st.markdown(html, unsafe_allow_html=True)
        st.link_button("📈 查看 K 線", row["K線連結"], use_container_width=True)


# ==========================================
# 9. 主程式
# ==========================================
try:
    with st.spinner("正在同步最新資料..."):
        df, warnings, errors = get_stock_base_data_v4()

    for msg in warnings:
        st.warning(msg)

    for msg in errors:
        st.error(msg)

    if df.empty:
        st.stop()

    with st.form("mobile_filter_form"):
        with st.expander("🎯 常用篩選條件", expanded=True):
            c1, c2 = st.columns(2)
            with c1:
                min_p = st.number_input("最低股價", value=0.0, step=1.0)
                min_v = st.number_input("最低成交量(張)", value=1000, step=100)
                target_industry = st.selectbox(
                    "篩選產業",
                    ["全部"] + sorted(df["industry"].dropna().astype(str).unique().tolist())
                )
            with c2:
                max_p = st.number_input("最高股價", value=500.0, step=1.0)
                max_pe = st.number_input("最高本益比(0為不限)", value=30.0, step=1.0)
                max_analyze = st.number_input(
                    "最多分析檔數",
                    value=MAX_ANALYZE_DEFAULT,
                    min_value=20,
                    max_value=300,
                    step=10
                )

        with st.expander("🧠 進階策略設定", expanded=False):
            enable_drawdown = st.checkbox("開啟「回檔策略」", value=False)
            enable_strong = st.checkbox("開啟「近期強勢群組」", value=False)

            dynamic_threshold = False
            support_mode = "全部符合"
            min_dd = 0
            min_change = 0

            if enable_drawdown:
                support_mode = st.selectbox("籌碼支撐型態", ["全部符合", "單日爆發強勢型", "波段洗刷接貨型"])
                dynamic_threshold = st.checkbox("啟用股本規模動態門檻調整", value=True)
                min_dd = st.slider("最低回檔幅度(%)", 0, 50, 5)

            if enable_strong:
                min_change = st.slider("最低今日漲幅(%)", -10, 10, 5)

        submitted = st.form_submit_button("🚀 開始分析", use_container_width=True)

    if not submitted:
        st.info("請先設定條件，然後按下「開始分析」。")
        st.stop()

    res = apply_base_filters(df, min_p, max_p, min_v, max_pe, target_industry)

    if not res.empty and len(res) > max_analyze:
        st.info("符合基礎條件共 {} 檔，為了加快手機分析速度，先取前 {} 檔進行技術分析。".format(len(res), int(max_analyze)))
        res = res.sort_values(by=["chip_ratio", "value_billion"], ascending=[False, False]).head(int(max_analyze)).copy()

    if not res.empty:
        codes = tuple(res["code"].astype(str).tolist())
        with st.spinner("正在批次分析 {} 檔股票技術指標...".format(len(codes))):
            tech_df = get_multi_stock_tech(codes, chunk_size=YF_CHUNK_SIZE)

        if not tech_df.empty:
            res = res.merge(tech_df, on="code", how="left")
        else:
            res["回檔%"] = 0.0
            res["今日漲幅%"] = 0.0
    else:
        res["回檔%"] = pd.Series(dtype="float32")
        res["今日漲幅%"] = pd.Series(dtype="float32")

    res["回檔%"] = res["回檔%"].fillna(0.0)
    res["今日漲幅%"] = res["今日漲幅%"].fillna(0.0)

    res = apply_strategy_filters(
        res=res,
        enable_drawdown=enable_drawdown,
        enable_strong=enable_strong,
        dynamic_threshold=dynamic_threshold,
        support_mode=support_mode,
        min_dd=min_dd,
        min_change=min_change
    )

    res = add_support_strength(res)
    res = add_etf_info(res)
    res = sort_result(res, enable_strong, enable_drawdown)
    display_df = build_display_df(res)

    active_strategies = []
    if enable_drawdown:
        active_strategies.append("回檔策略")
    if enable_strong:
        active_strategies.append("近期強勢群組")
    strategy_text = " 或 ".join(active_strategies) if active_strategies else "純基礎條件"

    st.success("🎯 當前過濾組合：【{}】｜ 最終符合條件：{} 檔".format(strategy_text, len(display_df)))

    if not display_df.empty:
        avg_chip = float(display_df["集中度"].mean()) if "集中度" in display_df.columns else 0.0
        avg_chg = float(display_df["今日漲幅%"].mean()) if "今日漲幅%" in display_df.columns else 0.0
        strong_cnt = int((display_df["支撐力道"] == "🔥 極強支撐").sum()) if "支撐力道" in display_df.columns else 0
        top_ind = "N/A"

        if "產業" in display_df.columns:
            mode_series = display_df["產業"].mode()
            if not mode_series.empty:
                top_ind = mode_series.iloc[0]

        m1, m2 = st.columns(2)
        with m1:
            st.metric("符合檔數", len(display_df))
            st.metric("平均集中度", "{:.2f}%".format(avg_chip))
        with m2:
            st.metric("平均漲幅", "{:.2f}%".format(avg_chg))
            st.metric("極強支撐", strong_cnt)

        st.caption("熱門產業：{}".format(top_ind))

    display_mode = st.radio(
        "結果顯示方式",
        ["卡片模式", "表格模式"],
        horizontal=True,
        index=0
    )

    if display_df.empty:
        st.info("目前沒有符合條件的股票。")
    else:
        final_cols = ["代號", "名稱", "產業", "今日漲幅%", "股價", "回檔%", "集中度", "支撐力道", "成交額", "本益比", "K線連結"]

        if display_mode == "卡片模式":
            render_mobile_cards(display_df[final_cols])
        else:
            st.dataframe(
                display_df[final_cols],
                column_config={
                    "代號": st.column_config.Column(width="small"),
                    "今日漲幅%": st.column_config.NumberColumn(format="%.2f %%"),
                    "股價": st.column_config.NumberColumn(format="%.2f"),
                    "回檔%": st.column_config.NumberColumn(format="%.2f %%"),
                    "集中度": st.column_config.NumberColumn(format="%.2f %%"),
                    "成交額": st.column_config.NumberColumn(format="%.2f 億"),
                    "本益比": st.column_config.NumberColumn(format="%.2f"),
                    "K線連結": st.column_config.LinkColumn("K線", display_text="📈查看")
                },
                use_container_width=True,
                hide_index=True,
                height=560
            )

except Exception as e:
    st.error("⚠️ 系統執行異常：{}".format(e))
