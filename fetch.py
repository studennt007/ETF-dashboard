import pandas as pd
import requests
import os
import time
from datetime import datetime
from io import StringIO
import re

# 確保 data 資料夾存在
os.makedirs('data', exist_ok=True)

# ETF 目標清單
etf_data = {
    "00981A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00981A.TW",
    "00982A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00982A.TW",
    "00403A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00403A.TW",
    "00980A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00980A.TW",
    "00992A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00992A.TW",
    "00985A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00985A.TW",
    "00991A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00991A.TW",
    "00987A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00987A.TW",
    "00994A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00994A.TW",
    "00995A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00995A.TW",
    "00993A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00993A.TW",
    "00996A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00996A.TW",
    "00400A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00400A.TW",
    "00401A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00401A.TW",
    "00999A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00999A.TW",
    "00405A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00405A.TW",
    "00407A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00407A.TW",
    "00406A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00406A.TW",
    "00984A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00984A.TW",
    "00404A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00404A.TW",

}

headers = {'User-Agent': 'Mozilla/5.0'}


def extract_data_date(html_text):
    """
    從網頁原始文字中，精準抓出『資料日期』標籤後面的日期。
    只信任明確標註「資料日期」的文字，避免誤抓到網頁其他系統時間戳記
    （例如查詢時間、網頁更新時間等）。
    回傳格式統一為 YYYYMMDD 字串；抓不到則回傳 None。
    """
    pattern = r'資料日期[:：]\s*(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})'
    match = re.search(pattern, html_text)

    if match:
        y, m, d = match.groups()
        try:
            dt = datetime(int(y), int(m), int(d))
            return dt.strftime('%Y%m%d')
        except ValueError:
            return None

    return None


print(f"--- 啟動更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

for code, url in etf_data.items():
    try:
        print(f"[{code}] 正在抓取成分股列表...")
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'

        # 先解析出「資料本身的日期」，而不是抓取當下的系統時間
        data_date = extract_data_date(response.text)

        if data_date is None:
            print(f"[{code}] ⚠️ 無法從頁面解析出『資料日期』標籤，跳過此檔，避免寫入錯誤日期的檔案。")
            time.sleep(1)
            continue

        output_path = os.path.join('data', f"{code}_{data_date}.csv")

        # 如果這個資料日期的檔案已經存在，代表資料還沒更新（假日/未開盤），
        # 直接跳過，避免重複寫入、也避免之後分析誤判成「有變動」
        if os.path.exists(output_path):
            print(f"[{code}] 資料日期 {data_date} 已存在對應檔案，資料尚未更新，跳過。")
            time.sleep(1)
            continue

        # 讀取網頁表格
        df = pd.read_html(StringIO(response.text))[1]

        # 提取代號
        df['ticker'] = df['個股名稱'].apply(
            lambda x: re.search(r'\((.*)\)', x).group(1) if re.search(r'\((.*)\)', x) else None
        )

        # 僅保留需要的欄位
        output_df = df[['個股名稱', '持有股數', '投資比例(%)', 'ticker']]

        output_df.to_csv(output_path, index=False, encoding='utf-8-sig')

        print(f"[{code}] 成功寫入檔案: {output_path} (資料日期: {data_date})")

        time.sleep(2)

    except Exception as e:
        print(f"[{code}] 處理時發生錯誤: {e}")

print("--- 更新流程結束 ---")
