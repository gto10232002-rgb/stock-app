<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>台股自選股看盤後台 - 行動版優化</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #121214; /* 採用專業看盤暗色調，護眼且對比高 */
            color: #ffffff;
            margin: 0;
            padding: 12px;
        }

        .stock-container {
            width: 100%;
            background-color: #1a1a1e;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 10px rgba(0,0,0,0.3);
        }

        /* 標頭欄位 */
        .stock-header {
            display: flex;
            background-color: #26262b;
            padding: 10px 16px;
            font-size: 0.85rem;
            color: #90909a;
            border-bottom: 1px solid #2d2d35;
        }

        /* 股票列表列 */
        .stock-row {
            display: flex;
            align-items: center;
            padding: 14px 16px;
            border-bottom: 1px solid #2d2d35;
            transition: background-color 0.2s;
        }
        .stock-row:active {
            background-color: #26262b; /* 手機點擊反饋 */
        }

        /* 關鍵修改 1：左側資訊固定區，靠左對齊 */
        .left-info-block {
            flex: 0 0 130px; /* 固定寬度，確保手機上不會被右側數據擠壓 */
            display: flex;
            flex-direction: column;
            align-items: flex-start; /* 確保所有文字、標籤絕對靠左 */
            justify-content: center;
        }

        .stock-name-code {
            display: flex;
            align-items: baseline;
            gap: 6px;
            margin-bottom: 4px;
        }

        .stock-name {
            font-size: 1.05rem;
            font-weight: bold;
            color: #ffffff;
        }

        .stock-code {
            font-size: 0.8rem;
            color: #8e8e93;
        }

        /* 補回：特定族群資訊標籤（如概念股、產業類股） */
        .sector-tag {
            font-size: 0.75rem;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: 500;
            background-color: #2c2c35;
            color: #3a9ad9; /* 族群資訊使用亮眼藍色，方便手機閱讀 */
            border: 1px solid #3a9ad9;
        }

        /* 關鍵修改 2：右側數據滾動區 */
        .right-data-block {
            flex: 1;
            display: flex;
            justify-content: space-between;
            align-items: center;
            overflow-x: auto; /* 手機寬度不夠時自動啟用水平滑動 */
            padding-left: 10px;
        }

        .data-item {
            flex: 1;
            text-align: right;
            min-width: 70px; /* 確保數據有基本寬度，不擠壓變形 */
            font-size: 1.05rem;
            font-weight: 600;
        }

        /* 台股顏色視覺規範 */
        .up-trend { color: #ff3b30; }   /* 漲：紅 */
        .down-trend { color: #34c759; } /* 跌：綠 */
        .flat-trend { color: #ffffff; } /* 平 */

        .volume-text {
            color: #aeaea3;
            font-size: 0.9rem;
        }
    </style>
</head>
<body>

<div class="stock-container">
    <div class="stock-header">
        <div style="flex: 0 0 130px; text-align: left;">股票 / 特定族群</div>
        <div style="flex: 1; display: flex; justify-content: space-between; text-align: right; padding-left: 10px;">
            <div style="flex: 1; text-align: right;">成交</div>
            <div style="flex: 1; text-align: right;">漲跌幅</div>
            <div style="flex: 1; text-align: right;">單量</div>
        </div>
    </div>

    <div class="stock-row">
        <div class="left-info-block">
            <div class="stock-name-code">
                <span class="stock-name">台積電</span>
                <span class="stock-code">2330</span>
            </div>
            <span class="sector-tag">半導體．AI概念</span>
        </div>
        <div class="right-data-block">
            <div class="data-item up-trend">985</div>
            <div class="data-item up-trend">+2.6%</div>
            <div class="data-item volume-text">1,245</div>
        </div>
    </div>

    <div class="stock-row">
        <div class="left-info-block">
            <div class="stock-name-code">
                <span class="stock-name">鴻海</span>
                <span class="stock-code">2317</span>
            </div>
            <span class="sector-tag">蘋果供應鏈</span>
        </div>
        <div class="right-data-block">
            <div class="data-item down-trend">210</div>
            <div class="data-item down-trend">-1.4%</div>
            <div class="data-item volume-text">856</div>
        </div>
    </div>

    <div class="stock-row">
        <div class="left-info-block">
            <div class="stock-name-code">
                <span class="stock-name">長榮</span>
                <span class="stock-code">2603</span>
            </div>
            <span class="sector-tag">航運族群</span>
        </div>
        <div class="right-data-block">
            <div class="data-item flat-trend">185</div>
            <div class="data-item flat-trend">0.0%</div>
            <div class="data-item volume-text">432</div>
        </div>
    </div>
</div>

</body>
</html>
