import streamlit as st
import pandas as pd
import requests
import datetime
import time
import yfinance as yf

# 頁面配置
st.set_page_config(page_title="StockTool", layout="wide")
st.markdown("### 📊 台股籌碼選股")

# 注入特製的手機行動端網頁表格 CSS（消滅滾動條、優化字體與對照體驗）
st.markdown("""
<style>
    .phone-table-container {
        width: 100%;
        overflow-x: hidden;
        margin-top: 10px;
    }
    .phone-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 14px;
    }
    .phone-table th {
        background-color: #f1f3f5;
        color: #333;
        font-weight: bold;
        text-align: left;
        padding: 8px 6px;
        border-bottom: 2px solid #dee2e6;
    }
    .phone-table td {
        padding: 10px 6px;
        border-bottom: 1px solid #dee2e6;
        vertical-align: middle;
    }
    /* 暗色模式相容 */
    html[data-theme="dark"] .phone-table th {
        background-color: #262730;
        color: #eee;
        border-bottom: 2px solid #464855;
    }
    html[data-theme="dark"] .phone-table td {
        border-bottom: 1px solid #464855;
    }
    .stock-link {
        color: #ff4b4b;
        text-decoration: none;
        font-weight: bold;
        display: block;
    }
    .badge {
        display: inline-block;
        padding: 2px 6px;
        font-size: 11px;
        font-weight: bold;
        border-radius: 4px;
        color: white;
    }
    .badge-danger { background-color: #dc3545; }
    .badge-success { background-color: #28a745; }
    .badge-info { background-color: #17a2b8; }
    .badge-secondary { background-color: #6c757d; }
</style>
""", unsafe_allow_html=True)

# 快取功能 1：抓取證交所基本與籌碼資料 (每小時更新一次)
@st.cache_data(ttl=3600)
def get_stock_base_data():
    url_price = "https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL"
    res_price = requests.get(url_price, timeout=20)
    df_price = pd.DataFrame()
    if res_price.status_code == 200:
        raw_price = pd.DataFrame(res_price.json())
        df_price = raw_price[raw_price['Code'].str.len() == 4].copy()
        df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].str.replace(',', ''), errors='coerce')
        df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].str.replace(',', ''), errors='coerce') / 1000
        df_price['trade_value'] = pd.to_numeric(raw_price['TradeValue'].str.replace(',', ''), errors='coerce')
        df_price = df_price[['Code', 'Name', 'price', 'vol', 'trade_value']].rename(columns={'Code': 'code', 'Name': 'name'})

    url_pe = "https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL"
    res_pe = requests.get(url_pe, timeout=20)
    df_pe = pd.DataFrame()
    if res_pe.status_code == 200:
        raw_pe = pd.DataFrame(res_pe.json())
        df_pe = raw_pe[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
        df_pe['pe'] = pd.to_numeric(df_pe['pe'].str.replace(',', ''), errors='coerce')

    df_chips = pd.DataFrame()
    headers = {'User-Agent': 'Mozilla/5.0'}
    for i in range(7):
        date_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={date_str}&selectType=ALLBUT0999&response=json"
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code == 200 and "data" in res.json():
            data = res.json()["data"]
            fields = res.json()["fields"]
            df_raw = pd.DataFrame(data, columns=fields)
            df_raw.columns = df_raw.columns.str.strip()
            fi_col = [c for c in df_raw.columns if '外資' in c and '買賣超股數' in c][0]
            it_col = [c for c in df_raw.columns if '投信' in c and '買賣超股數' in c][0]
            df_chips['code'] = df_raw['證券代號'].astype(str).str.strip()
            df_chips['fi'] = pd.to_numeric(df_raw[fi_col].str.replace(',', ''), errors='coerce') / 1000
            df_chips['it'] = pd.to_numeric(df_raw[it_col].str.replace(',', ''), errors='coerce') / 1000
            break
        time.sleep(0.5)

    if df_price.empty or df_chips.empty:
        return pd.DataFrame()
        
    df = pd.merge(df_price, df_chips, on='code', how='inner')
    df = pd.merge(df, df_pe, on='code', how='left')
    df['chip_ratio'] = ((df['fi'] + df['it']) / df['vol'] * 100).round(2)
    df['value_billion'] = (df['trade_value'] / 100000000).round(2)
    return df

# 快取功能 2：獨立快取每檔股票的 yfinance 回檔率
@st.cache_data(ttl=3600)
def get_single_drawdown(code):
    try:
        hist = yf.Ticker(f"{code}.TW").history(period="1mo")
        if not hist.empty:
            high_1m = hist['High'].max()
            current = hist['Close'].iloc[-1]
            if high_1m > 0:
                return round(((high_1m - current) / high_1m) * 100, 2)
    except:
        pass
    return 0.0

# --- 主程式區塊 ---
try:
    with st.spinner("正在同步最新籌碼數據..."):
        df = get_stock_base_data()
    
    if df.empty:
        st.warning("暫時無法取得證交所資料，請確認開盤日或稍後再試。")
    else:
        # 側邊欄：基礎篩選
        st.sidebar.header("🎯 基礎篩選條件")
        min_p = st.sidebar.number_input("最低股價", value=0.0)
        max_p = st.sidebar.number_input("最高股價", value=500.0)
        min_v = st.sidebar.number_input("最低成交量(張)", value=1000)
        max_pe = st.sidebar.number_input("最高本益比 (0為不限)", value=30.0)
        
        # 進階篩選設定
        st.sidebar.header("🛡️ 進階篩選設定")
        apply_lei_rules = st.sidebar.checkbox("是否套用雷老闆實務心法篩選", value=True)
        
        if apply_lei_rules:
            support_mode = st.sidebar.selectbox(
                "└ 籌碼支撐型態",
                ["全部符合", "單日爆發強勢型 (集中度>5%)", "波段洗刷接貨型 (高回檔+法人守穩)"]
            )
            dynamic_threshold = st.sidebar.checkbox(
                "└ 啟用股本規模動態門檻調整", 
                value=True
            )
            min_dd = st.sidebar.slider("└ 最低回檔幅度(%)", 0, 50, 5)
        
        # --- 第一階段：基礎與基本面篩選 ---
        res = df[(df['price'] >= min_p) & (df['price'] <= max_p) & (df['vol'] >= min_v)].copy()
        if max_pe > 0:
            res = res[(res['pe'] > 0) & (res['pe'] <= max_pe)]
            
        # --- 第二階段：根據總開關決定是否套用籌碼與回檔心法 ---
        if apply_lei_rules:
            if dynamic_threshold:
                cond_large = (res['value_billion'] >= 5.0) & (res['chip_ratio'] >= 2.5)
                cond_small = (res['value_billion'] < 5.0) & (res['chip_ratio'] >= 5.0)
                res = res[cond_large | cond_small]
                
            if support_mode == "單日爆發強勢型 (集中度>5%)":
                res = res[res['chip_ratio'] >= 5.0]
                
            if not res.empty:
                with st.spinner(f"正在分析 {len(res)} 檔目標個股的歷史回檔波動..."):
                    res['回檔%'] = res['code'].apply(get_single_drawdown)
                
                res = res[res['回檔%'] >= min_dd]
                
                if support_mode == "波段洗刷接貨型 (高回檔+法人守穩)":
                    res = res[res['回檔%'] >= max(8.0, min_dd)]
            else:
                res['回檔%'] = pd.Series(dtype=float)

            def judge_support_strength(row):
                if row['chip_ratio'] >= 10.0:
                    return '<span class="badge badge-danger">🔥強爆發</span>'
                elif row['chip_ratio'] >= 5.0:
                    return '<span class="badge badge-success">✅健康買</span>'
                elif row['value_billion'] >= 5.0 and row['chip_ratio'] >= 2.5:
                    return '<span class="badge badge-info">🏛️法人撐</span>'
                else:
                    return '<span class="badge badge-secondary">观察中</span>'

            if not res.empty:
                res['支撐力道'] = res.apply(judge_support_strength, axis=1)
                res = res.sort_values(by=['chip_ratio', '回檔%'], ascending=[False, False])
            else:
                res['支撐力道'] = pd.Series(dtype=str)
                
        else:
            res['回檔%'] = 0.0
            res['支撐力道'] = '<span class="badge badge-secondary">未啟用</span>'
            if not res.empty:
                res = res.sort_values(by='chip_ratio', ascending=False)

        # 輸出統計結果
        st.success(f"🎯 篩選完畢，最終符合條件：{len(res)} 檔")
        
        # --- 【核心重頭戲】特製無滾動條、高對照性手機端 HTML 表格 ---
        if res.empty:
            st.info("無符合當前條件的股票，請調整左側篩選標準。")
        else:
            # 建立表格表頭
            table_html = """
            <div class="phone-table-container">
                <table class="phone-table">
                    <thead>
                        <tr>
                            <th style="width: 28%;">股票</th>
                            <th style="width: 18%;">現價</th>
                            <th style="width: 18%;">回檔</th>
                            <th style="width: 18%;">集中</th>
                            <th style="width: 20%;">支撐力道</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            # 填入每一列數據
            for idx, row in res.iterrows():
                yahoo_url = f"https://tw.stock.yahoo.com/quote/{row['code']}"
                table_html += f"""
                        <tr>
                            <td>
                                <a class="stock-link" href="{yahoo_url}" target="_blank">{row['code']}<br><span style="font-size:12px;color:#666;">{row['name']}</span></a>
                            </td>
                            <td><b>{row['price']:.1f}</b></td>
                            <td>{row['回檔%']:.1f}%</td>
                            <td>{row['chip_ratio']:.1f}%</td>
                            <td>{row['支撐力道']}</td>
                        </tr>
                """
            
            table_html += """
                    </tbody>
                </table>
            </div>
            """
            
            # 使用 markdown 將精簡表格渲染到畫面上
            st.markdown(table_html, unsafe_allow_html=True)

except Exception as e:
    st.error(f"程式發生錯誤: {e}")
