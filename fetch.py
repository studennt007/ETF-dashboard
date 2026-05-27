import pandas as pd
import requests
import os
import yfinance as yf
import time
import glob
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

def get_latest_market_data(ticker):
    """取得最新市場資訊：最後交易日期、漲跌幅、漲跌價、成交量"""
    try:
        yf_ticker = yf.Ticker(ticker)
        # 增加緩衝時間，避免請求過快被鎖
        hist = yf_ticker.history(period="5d")
        if len(hist) < 2: return None
        
        last_date = hist.index[-1].strftime('%Y%m%d')
        prev_close = hist['Close'].iloc[-2]
        curr_price = hist['Close'].iloc[-1]
        volume = int(hist['Volume'].iloc[-1])
        
        change = curr_price - prev_close
        pct = (change / prev_close) * 100
        return last_date, round(float(pct), 2), round(float(change), 2), volume
    except Exception as e:
        print(f"yfinance 錯誤 ({ticker}): {e}")
        return None

# 主程式
print(f"--- 啟動更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

for code, url in etf_data.items():
    try:
        print(f"[{code}] 正在抓取成分股列表...")
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        df = pd.read_html(StringIO(response.text))[1]
        
        # 提取代號
        df['ticker'] = df['個股名稱'].apply(lambda x: re.search(r'\((.*)\)', x).group(1) if re.search(r'\((.*)\)', x) else None)
        
        # 取得基準日期 (使用該 ETF 本身的最新交易日)
        latest_info = get_latest_market_data(f"{code}.TW")
        if not latest_info:
            print(f"[{code}] 無法取得基準市場數據，跳過。")
            continue
        last_date = latest_info[0]
        
        # 批次處理每檔個股行情
        print(f"[{code}] 正在計算成分股漲跌 (日期: {last_date})...")
        processed_data = []
        for t in df['ticker'].dropna():
            info = get_latest_market_data(f"{t}.TW")
            processed_data.append(info[1:4] if info else (0.0, 0.0, 0))
        
        df['今日漲跌幅%'], df['今日漲跌價'], df['Volume'] = zip(*processed_data)
        
        # 強制寫入路徑
        output_path = os.path.join('data', f"{code}_{last_date}.csv")
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"[{code}] 成功寫入檔案: {output_path}")
        
        time.sleep(2) # 避免 API 頻率限制
        
    except Exception as e:
        print(f"處理 {code} 時發生錯誤: {e}")

print("--- 更新流程結束 ---")
