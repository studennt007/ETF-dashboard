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

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Referer': 'https://www.moneydj.com/',
}


def extract_data_date(html_text):
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


def fetch_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                response.encoding = 'utf-8'
                return response
            elif response.status_code == 403 and attempt < max_retries - 1:
                time.sleep(3)
                continue
            else:
                response.raise_for_status()
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            else:
                raise
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            else:
                raise
    
    return None


print(f"--- 啟動更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

for code, url in etf_data.items():
    try:
        print(f"[{code}] 正在抓取成分股列表...")
        response = fetch_with_retry(url)
        
        if response is None:
            print(f"[{code}] 無法連線，跳過此檔")
            time.sleep(1)
            continue

        data_date = extract_data_date(response.text)

        if data_date is None:
            print(f"[{code}] ⚠️ 無法從頁面解析出『資料日期』標籤，跳過此檔。")
            time.sleep(1)
            continue

        output_path = os.path.join('data', f"{code}_{data_date}.csv")

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

        # 提取網頁上的「持有股數 / 口數」，並重新命名改回原本的「持有股數」
        output_df = df[['個股名稱', '持有股數 / 口數', '投資比例(%)', 'ticker']].copy()
        output_df = output_df.rename(columns={'持有股數 / 口數': '持有股數'})

        # 寫入 CSV 檔案
        output_df.to_csv(output_path, index=False, encoding='utf-8-sig')

        print(f"[{code}] 成功寫入檔案: {output_path} (資料日期: {data_date})")

        time.sleep(2)

    except Exception as e:
        print(f"[{code}] 處理時發生錯誤: {e}")

print("--- 更新流程結束 ---")
