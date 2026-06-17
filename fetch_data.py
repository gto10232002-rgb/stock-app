# fetch_data.py
import requests
import pandas as pd
import numpy as np
import datetime
import yfinance as yf
import concurrent.futures
from io import StringIO

def get_stock_base_data():
    cols = ['code', 'name', 'price', 'vol', 'trade_value', 'pe', 'industry', 'chip_ratio', 'value_billion']
    empty_df = pd.DataFrame(columns=cols)
    chip_success = False
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    # 1. 抓取大盤價格 (主線)
    df_price = pd.DataFrame()
    try:
        res_p = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=headers, timeout=15)
        if res_p.status_code == 200:
            raw = pd.DataFrame(res_p.json())
            if not raw.empty and 'Code' in raw.columns:
                df_price = raw.copy()
    except Exception:
        pass

    # 備用防線 (Open Data)
    if df_price.empty:
        try:
            res_fb = requests.get("https://www.twse.com.tw/exchangeReport/STOCK_DAY_ALL?response=open_data", headers=headers, timeout=15)
            if res_fb.status_code == 200:
                df_fb = pd.read_csv(StringIO(res_fb.text), dtype=str)
                df_price = df_fb.rename(columns={'證券代號': 'Code', '證券名稱': 'Name', '收盤價': 'ClosingPrice', '成交股數': 'TradeVolume', '成交金額': 'TradeValue'})
        except Exception:
            return empty_df

    if df_price.empty:
        return empty_df

    # 格式化價格與量能
    df_price = df_price[df_price['Code'].str.len() == 4].copy()
    df_price['price'] = pd.to_numeric(df_price['ClosingPrice'].astype(str).str.replace(',', ''), errors='coerce')
    df_price['vol'] = pd.to_numeric(df_price['TradeVolume'].astype(str).str.replace(',', ''), errors='coerce') / 1000
    df_price['trade_value'] = pd.to_numeric(df_price['TradeValue'].astype(str).str.replace(',', ''), errors='coerce')
    df_price = df_price[['Code', 'Name', 'price', 'vol', 'trade_value']].rename(columns={'Code': 'code', 'Name': 'name'})
    df_price = df_price[~df_price['code'].str.startswith('91')]

    # 2. 抓取本益比
    df_pe = pd.DataFrame()
    try:
        res_pe = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL", headers=headers, timeout=15)
        if res_pe.status_code == 200:
            df_pe = pd.DataFrame(res_pe.json())[['Code', 'PEratio']].rename(columns={'Code': 'code', 'PEratio': 'pe'})
        if df_pe.empty:
            res_pe_fb = requests.get("https://www.twse.com.tw/exchangeReport/BWIBBU_ALL?response=open_data", headers=headers, timeout=15)
            df_fb_pe = pd.read_csv(StringIO(res_pe_fb.text), dtype=str)
            df_pe = df_fb_pe[['證券代號', '本益比']].rename(columns={'證券代號': 'code', '本益比': 'pe'})
        df_pe['pe'] = pd.to_numeric(df_pe['pe'].astype(str).str.replace(',', ''), errors='coerce')
    except Exception:
        pass

    # 3. 抓取產業別
    df_ind = pd.DataFrame()
    try:
        res_ind = requests.get("https://openapi.twse.com.tw/v1/opendata/t187ap03_L", headers=headers, timeout=15)
        if res_ind.status_code == 200:
            df_ind = pd.DataFrame(res_ind.json())[['公司代號', '產業別']].rename(columns={'公司代號': 'code', '產業別': 'industry'})
    except Exception:
        pass

    # 4. 追溯 7 天籌碼資料
    df_chips = pd.DataFrame()
    for i in range(7):
        d_str = (datetime.datetime.now() - datetime.timedelta(days=i)).strftime("%Y%m%d")
        url = f"https://www.twse.com.tw/rwd/zh/fund/T86?date={d_str}&selectType=ALLBUT0999&response=json"
        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                js = res.json()
                if "data" in js:
                    df_raw = pd.DataFrame(js["data"], columns=[c.strip() for c in js["fields"]])
                    fi_c = [c for c in df_raw.columns if '外資' in c and '買賣超' in c][0]
                    it_c = [c for c in df_raw.columns if '投信' in c and '買賣超' in c][0]
                    df_chips['code'] = df_raw['證券代號'].astype(str).str.strip()
                    df_chips['fi'] = pd.to_numeric(df_raw[fi_c].str.replace(',', ''), errors='coerce') / 1000
                    df_chips['it'] = pd.to_numeric(df_raw[it_c].str.replace(',', ''), errors='coerce') / 1000
                    chip_success = True
                    break
        except Exception:
            continue

    # 資料流合併
    if chip_success and not df_chips.empty:
        df = pd.merge(df_price, df_chips, on='code', how='left').fillna(0.0)
        df['chip_ratio'] = ((df['fi'] + df['it']) / df['vol'].replace(0, np.nan)) * 100
        df['chip_ratio'] = df['chip_ratio'].clip(upper=100.0).round(2)
    else:
        df = df_price.copy()
        df['chip_ratio'] = np.nan 

    df['value_billion'] = (df['trade_value'] / 100000000).round(2)
    df = pd.merge(df, df_pe, on='code', how='left') if not df_pe.empty else df.assign(pe=np.nan)
    df = pd.merge(df, df_ind, on='code', how='left') if not df_ind.empty else df.assign(industry='其他')

    # 產業對照清洗
    ind_map = {"24": "半導體業", "25": "電腦及週邊設備業", "26": "光電業", "27": "通信網路業", "28": "電子零組件業", "29": "電子通路業", "30": "資訊服務業", "31": "其他電子業", "14": "建材營建", "15": "航運業", "17": "金融保險"}
    df['industry'] = df['industry'].apply(lambda x: str(x).strip()[:-2] if str(x).strip().endswith('.0') else str(x).strip())
    df['industry'] = df['industry'].map(ind_map).fillna("其他")

    return df[cols], chip_success

def get_single_stock_tech(c):
    tk = f"{str(c).strip()}.TW"
    try:
        hist = yf.download(tk, period="1mo", progress=False, timeout=10)
        if not hist.empty and 'Close' in hist.columns and 'High' in hist.columns:
            if isinstance(hist.columns, pd.MultiIndex):
                hist.columns = [col[0] for col in hist.columns]
            closes, highs = hist['Close'].dropna(), hist['High'].dropna()
            if len(closes) >= 2:
                h_max, cur, prev = float(highs.max()), float(closes.iloc[-1]), float(closes.iloc[-2])
                return c, round(((h_max - cur) / h_max) * 100, 2), round(((cur - prev) / prev) * 100, 2)
    except Exception:
        pass
    return c, np.nan, np.nan

if __name__ == "__main__":
    print("🚀 [後台排程] 開始下載台股盤後數據...")
    df, chip_ok = get_stock_base_data()
    
    if not df.empty:
        print(f"📈 成功取得 {len(df)} 檔基本資料。開始多執行緒計算技術指標...")
        codes = df['code'].tolist()
        dd_map, chg_map = {}, {}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = executor.map(get_single_stock_tech, codes)
            
        for c, dd, chg in results:
            dd_map[c] = dd
            chg_map[c] = chg
            
        df['回檔%'] = df['code'].map(dd_map)
        df['今日漲幅%'] = df['code'].map(chg_map)
        df['chip_success'] = 1 if chip_ok else 0
        
        # 儲存為本地靜態檔案
        df.to_csv("stock_data.csv", index=False, encoding="utf-8-sig")
        print("💾 [成功] 資料已完美融合成 stock_data.csv！")
    else:
        print("❌ [失敗] 證交所未回傳任何資料，本次不覆蓋歷史資料庫。")
