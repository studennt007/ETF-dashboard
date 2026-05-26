import pandas as pd
import requests
import os
import yfinance as yf
import twstock
import time
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

def get_stock_metrics(ticker):
    """
    計算漲跌幅與漲跌價
    邏輯：(最新價格 - 昨日收盤價) / 昨日收盤價
    """
    code = str(ticker).split('.')[0]
    
    # 1. 嘗試 yfinance
    try:
        yf_ticker = yf.Ticker(ticker)
        hist = yf_ticker.history(period="5d")
        if len(hist) >= 2:
            # 取得最後兩筆交易日數據
            prev_close = hist['Close'].iloc[-2]
            curr_price = hist['Close'].iloc[-1]
            change = curr_price - prev_close
            pct = (change / prev_close) * 100
            return round(float(pct), 2), round(float(change), 2)
    except:
        pass

    # 2. 若 yfinance 失敗，嘗試 twstock (針對台股專用)
    try:
        stock = twstock.Stock(code)
        data = stock.fetch_31() # 取得近期資料
        if len(data) >= 2:
            prev_close = data[-2].close
            curr_price = data[-1].close
            change = curr_price - prev_close
            pct = (change / prev_close) * 100
            return round(float(pct), 2), round(float(change), 2)
    except:
        pass
    
    return 0.0, 0.0 # 若兩者皆查不到，回傳 0

# 主程式執行區
for code, url in etf_data.items():
    print(f"--- 正在處理 {code} ---")
    try:
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        df = pd.read_html(StringIO(response.text))[1]
        
        # 提取括號內代號
        df['ticker'] = df['個股名稱'].apply(lambda x: re.search(r'\((.*)\)', x).group(1) if re.search(r'\((.*)\)', x) else None)
        
        print("正在獲取最新股價與漲跌資訊...")
        # 批次運算漲跌幅與漲跌價
        results = df['ticker'].apply(get_stock_metrics)
        df['今日漲跌幅%'], df['今日漲跌價'] = zip(*results)
        
        # 存檔
        output_path = f"data/{code}_{datetime.now().strftime('%Y%m%d')}.csv"
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"成功更新 {code}，檔案已存至: {output_path}")
        
        time.sleep(1.5) # 避免頻繁訪問被鎖 IP
        
    except Exception as e:
        print(f"處理 {code} 時發生錯誤: {e}")