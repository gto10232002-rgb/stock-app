<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>台股行動版自選股看盤清單</title>
    <style>
        /* 全域基本設定，採用專業暗黑模式看盤介面 */
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: #0f0f11;
            color: #ffffff;
            margin: 0;
            padding: 8px;
        }

        /* 【關鍵修正 1】將滾動控制設在最外層，確保標頭與所有數據「同步水平滑動」 */
        .watchlist-scroll-container {
            width: 100%;
            overflow-x: auto; 
            -webkit-overflow-scrolling: touch; /* 讓 iOS 滑動更流暢 */
            background-color: #16161a;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
        }

        /* 看盤表格主體 */
        .stock-table {
            width: 100%;
            border-collapse: collapse;
            text-align: right;
            font-size: 0.95rem;
            white-space: nowrap; /* 防止手機上文字因寬度不足被自動斷行 */
        }

        /* 標頭欄位樣式 */
        .stock-table th {
            background-color: #212126;
            color: #8a8a93;
            font-size: 0.8rem;
            font-weight: 500;
            padding: 12px 10px;
            border-bottom: 1px solid #2d2d35;
        }

        /* 資料列基本樣式 */
        .stock-table td {
            padding: 14px 10px;
            border-bottom: 1px solid #23232a;
            vertical-align: middle;
        }

        /* 手機觸控點擊反饋 */
        .stock-table tbody tr:active {
            background-color: #212126;
        }

        /* 【關鍵修正 2】將第一欄（股票與族群）鎖定在最左側，不受滾動影響 */
        .stock-table th:first-child,
        .stock-table td:first-child {
            position: sticky;
            left: 0;
            text-align: left; /* 遵照指示：完全靠左對齊 */
            background-color: #16161a; /* 必須給予不透明背景，右側數據滑過來時才不會穿透疊字 */
            z-index: 2;
            width: 140px;
            min-width: 140px;
            box-shadow: 4px 0 8px rgba(0, 0, 0, 0.3); /* 右側加上陰影，視覺上做出分層感 */
        }

        /* 標頭第一欄層級調高，避免被資料列蓋住 */
        .stock-table th:first-child {
            background-color: #212126;
            z-index: 3;
        }

        /* 左側固定區塊佈局（垂直堆疊） */
        .stock-info-cell {
            display: flex;
            flex-direction: column;
            align-items: flex-start; /* 確保內容絕對靠左 */
            gap: 4px;
        }

        /* 股票名稱與代碼外殼 */
        .stock-meta {
            display: flex;
            align-items: baseline;
            gap: 6px;
        }

        .stock-name {
            font-size: 1.05rem;
            font-weight: bold;
            color: #ffffff;
        }

        .stock-code {
            font-size: 0.75rem;
            color: #8a8a93;
        }

        /* 【資訊補回】特定族群 / 概念股標籤樣式 */
        .sector-tag {
            font-size: 0.7rem;
            padding: 2px 6px;
            border-radius: 4px;
            background-color: rgba(58, 154, 217, 0.15);
            color: #4fc3f7; /*淡藍色，在暗色模式下極易辨識 */
            border: 1px solid rgba(58, 154, 217, 0.3);
            font-weight: normal;
        }

        /* 報價數據樣式 */
        .data-cell {
            font-weight: 600;
            font-size: 1.05rem;
        }

        /* 符合台股視覺規範（漲紅跌綠） */
        .trend-up { color: #ff3b30; }
        .trend-down { color: #34c759; }
        .trend-flat { color: #ffffff; }

        /* 次要數據（量、開高低）顏色淡化，凸顯重點 */
        .minor-text {
            color: #aeaeae;
            font-size: 0.9rem;
            font-weight: normal;
        }
    </style>
</head>
<body>

<div class="watchlist-scroll-container">
    <table class="stock-table">
        <thead>
            <tr>
                <th>股票 / 特定族群</th>
                <th>成交價</th>
                <th>漲跌</th>
                <th>漲跌幅</th>
                <th>單量</th>
                <th>總量</th>
                <th>開盤</th>
                <th>最高</th>
                <th>最低</th>
                <th>昨收</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>
                    <div class="stock-info-cell">
                        <div class="stock-meta">
                            <span class="stock-name">台積電</span>
                            <span class="stock-code">2330</span>
                        </div>
                        <span class="sector-tag">半導體．AI概念</span>
                    </div>
                </td>
                <td class="data-cell trend-up">985.00</td>
                <td class="data-cell trend-up">+25.0</td>
                <td class="data-cell trend-up">+2.60%</td>
                <td class="minor-text">142</td>
                <td class="minor-text">24,510</td>
                <td class="minor-text">970.00</td>
                <td class="minor-text">988.00</td>
                <td class="minor-text">968.00</td>
                <td class="minor-text">960.00</td>
            </tr>

            <tr>
                <td>
                    <div class="stock-info-cell">
                        <div class="stock-meta">
                            <span class="stock-name">聯發科</span>
                            <span class="stock-code">2454</span>
                        </div>
                        <span class="sector-tag">IC設計．手機晶片</span>
                    </div>
                </td>
                <td class="data-cell trend-down">1,380.00</td>
                <td class="data-cell trend-down">-20.0</td>
                <td class="data-cell trend-down">-1.43%</td>
                <td class="minor-text">85</td>
                <td class="minor-text">5,120</td>
                <td class="minor-text">1,405.00</td>
                <td class="minor-text">1,410.00</td>
                <td class="minor-text">1,375.00</td>
                <td class="minor-text">1,400.00</td>
            </tr>

            <tr>
                <td>
                    <div class="stock-info-cell">
                        <div class="stock-meta">
                            <span class="stock-name">鴻海</span>
                            <span class="stock-code">2317</span>
                        </div>
                        <span class="sector-tag">電動車．蘋果鏈</span>
                    </div>
                </td>
                <td class="data-cell trend-flat">210.00</td>
                <td class="data-cell trend-flat">0.0</td>
                <td class="data-cell trend-flat">0.00%</td>
                <td class="minor-text">312</td>
                <td class="minor-text">42,150</td>
                <td class="minor-text">210.00</td>
                <td class="minor-text">212.50</td>
                <td class="minor-text">208.00</td>
                <td class="minor-text">210.00</td>
            </tr>
        </tbody>
    </table>
</div>

</body>
</html>
