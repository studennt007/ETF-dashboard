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
# 精確 18 檔主動式 ETF 目標清單
etf_data = {
    # 第一批提到的 5 檔
    "00981A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00981A.TW", # 主動統一台股增長
    "00982A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00982A.TW", # 主動群益台灣強棒
    "00403A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00403A.TW", # 主動元大全球優質債券
    "00980A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00980A.TW", # 主動野村臺灣優選
    "00992A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00992A.TW", # 主動群益科技創新
    
    # 第二批追加的 13 檔
    "00985A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00985A.TW", # 主動野村台灣50
    "00991A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00991A.TW", # 主動復華未來50
    "00987A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00987A.TW", # 主動台新優勢成長
    "00994A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00994A.TW", # 主動第一金台股優
    "00995A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00995A.TW", # 主動中信台灣卓越
    "00993A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00993A.TW", # 主動安聯台灣
    "00996A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00996A.TW", # 主動兆豐台灣豐收
    "00400A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00400A.TW", # 主動國泰動能高息
    "00401A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00401A.TW", # 主動摩根台灣鑫收
    "00999A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00999A.TW", # 主動野村臺灣高息
    "00405A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00405A.TW", # 主動富邦台灣龍耀
    "00407A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00407A.TW", # 主動凱基台灣
    "00406A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00406A.TW"  # 主動中信台灣收益
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
