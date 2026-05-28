Markdown
# ETF Dashboard Project

## 專案功能
這是一個全自動化的 ETF 數據監控儀表板。

## 系統架構 (Data Pipeline)
1. **資料抓取 (Extract)**: 透過 Python 腳本抓取即時數據。
2. **自動化處理 (Transform & Load)**: 使用 GitHub Actions 每日定時執行 ETL 流程，將數據更新至 CSV 檔案。
3. **資料視覺化 (Dashboard)**: 利用 Streamlit 讀取最新 CSV 數據並呈現互動圖表。

## 專案亮點
* **全自動化**: 每日自動更新，實現零人工維護的 Data Pipeline。
* **技術堆疊**: Python, GitHub Actions, Streamlit。
