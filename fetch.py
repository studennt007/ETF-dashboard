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

# 取得當前日期作為檔名標記
current_date = datetime.now().strftime('%Y%m%d')

print(f"--- 啟動更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

for code, url in etf_data.items():
    try:
        print(f"[{code}] 正在抓取成分股列表...")
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        
        # 讀取網頁表格
        df = pd.read_html(StringIO(response.text))[1]
        
        # 提取代號
        df['ticker'] = df['個股名稱'].apply(lambda x: re.search(r'\((.*)\)', x).group(1) if re.search(r'\((.*)\)', x) else None)
        
        # 僅保留需要的欄位
        output_df = df[['個股名稱', '持有股數', '投資比例(%)', 'ticker']]
        
        # 修改點：使用代號_日期的格式
        output_path = os.path.join('data', f"{code}_{current_date}.csv")
        output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        print(f"[{code}] 成功寫入檔案: {output_path}")
        
        time.sleep(2)
        
    except Exception as e:
        print(f"[{code}] 處理時發生錯誤: {e}")

print("--- 更新流程結束 ---")
