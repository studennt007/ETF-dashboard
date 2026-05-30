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
current_date = datetime.now().strftime('%Y%m%d')

print(f"--- 啟動更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

for code, url in etf_data.items():
    try:
        print(f"[{code}] 正在抓取成分股...")
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        
        # 讀取網頁表格
        df = pd.read_html(StringIO(response.text))[1]
        df['ticker'] = df['個股名稱'].apply(lambda x: re.search(r'\((.*)\)', x).group(1) if re.search(r'\((.*)\)', x) else None)
        output_df = df[['個股名稱', '持有股數', '投資比例(%)', 'ticker']]
        
        # --- [優化核心] 智慧檢查：只在有變動時儲存 ---
        existing_files = sorted([f for f in os.listdir('data') if f.startswith(code)], reverse=True)
        should_save = True
        
        if existing_files:
            latest_df = pd.read_csv(os.path.join('data', existing_files[0]))
            # 比對新舊資料的內容 (忽略欄位順序)
            if output_df.equals(latest_df[['個股名稱', '持有股數', '投資比例(%)', 'ticker']]):
                should_save = False
        
        if should_save:
            output_path = os.path.join('data', f"{code}_{current_date}.csv")
            output_df.to_csv(output_path, index=False, encoding='utf-8-sig')
            print(f"[{code}] 偵測到持股變動，成功更新檔案: {output_path}")
        else:
            print(f"[{code}] 數據無變化，跳過寫入。")
        
        time.sleep(2)
        
    except Exception as e:
        print(f"[{code}] 處理時發生錯誤: {e}")

print("--- 更新流程結束 ---")
