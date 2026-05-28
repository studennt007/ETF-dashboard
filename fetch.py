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
    "00992A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00992A.TW"
}

headers = {'User-Agent': 'Mozilla/5.0'}

print(f"--- 啟動更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

for code, url in etf_data.items():
    try:
        print(f"[{code}] 正在抓取成分股列表...")
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        
        # 讀取網頁表格
        # MoneyDJ 的成分股列表通常在第 2 個表格 (index=1)
        df = pd.read_html(StringIO(response.text))[1]
        
        # 提取代號 (保留原本的邏輯)
        df['ticker'] = df['個股名稱'].apply(lambda x: re.search(r'\((.*)\)', x).group(1) if re.search(r'\((.*)\)', x) else None)
        
        # 僅保留需要的欄位
        output_df = df[['個股名稱', '持有股數', '投資比例(%)', 'ticker']]
        
        # 寫入檔案：改用固定檔名 {code}_latest.csv
        # 這樣 Git 每次比對的都是同一個檔案，變更會更清楚，也不會產生一堆垃圾日期檔案
        output_path = os.path.join('data', f"{code}_latest.csv")
        output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"[{code}] 成功寫入檔案: {output_path}")
        
        # 稍作停頓保護請求頻率
        time.sleep(2)
        
    except Exception as e:
        print(f"[{code}] 處理時發生錯誤: {e}")

print("--- 更新流程結束 ---")
