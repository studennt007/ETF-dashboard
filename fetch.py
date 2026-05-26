import pandas as pd
import requests
import os
import yfinance as yf
import time
import glob
from datetime import datetime
from io import StringIO
import re

# ETF 目標清單
etf_data = {
    "00981A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00981A.TW",
    "00982A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00982A.TW",
    "00403A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00403A.TW",
    "00980A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00980A.TW",
    "00992A": "https://www.moneydj.com/ETF/X/Basic/Basic0007B.xdjhtm?etfid=00992A.TW"
}

headers = {'User-Agent': 'Mozilla/5.0'}
if not os.path.exists('data'): os.makedirs('data')

def get_latest_market_data(ticker):
    """取得最新市場資訊：最後交易日期、漲跌幅、漲跌價、成交量"""
    try:
        yf_ticker = yf.Ticker(ticker)
        hist = yf_ticker.history(period="5d")
        if len(hist) < 2: return None
        
        last_date = hist.index[-1].strftime('%Y%m%d')
        prev_close = hist['Close'].iloc[-2]
        curr_price = hist['Close'].iloc[-1]
        volume = int(hist['Volume'].iloc[-1])
        
        change = curr_price - prev_close
        pct = (change / prev_close) * 100
        return last_date, round(float(pct), 2), round(float(change), 2), volume
    except:
        return None

# 主程式執行區
print(f"--- 啟動更新程式: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

for code, url in etf_data.items():
    try:
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        df = pd.read_html(StringIO(response.text))[1]
        df['ticker'] = df['個股名稱'].apply(lambda x: re.search(r'\((.*)\)', x).group(1) if re.search(r'\((.*)\)', x) else None)
        
        first_ticker = f"{df['ticker'].dropna().iloc[0]}.TW"
        latest_info = get_latest_market_data(first_ticker)
        
        if not latest_info:
            print(f"[{code}] 無法取得市場數據，跳過。")
            continue
            
        last_date, pct, change, volume = latest_info
        
        # 檢查機制：若已有今日檔案或成交量沒變，則跳過
        files = sorted(glob.glob(f"data/{code}_*.csv"))
        if files:
            last_file = files[-1]
            if last_date in last_file:
                print(f"[{code}] 資料已是最新的 (日期: {last_date})，跳過。")
                continue
        
        print(f"[{code}] 資料更新中...")
        # 批次運算
        results = df['ticker'].apply(lambda t: get_latest_market_data(f"{t}.TW")[1:4] if get_latest_market_data(f"{t}.TW") else (0.0, 0.0, 0))
        df['今日漲跌幅%'], df['今日漲跌價'], df['Volume'] = zip(*results)
        
        output_path = f"data/{code}_{last_date}.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"[{code}] 更新成功，存檔至: {output_path}")
        
        time.sleep(1.5)
        
    except Exception as e:
        print(f"處理 {code} 時發生錯誤: {e}")

print("--- 所有任務檢查完畢，目前資料皆為最新 ---")