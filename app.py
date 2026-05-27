import streamlit as st
import pandas as pd
import os
import plotly.express as px
import yfinance as yf
from functools import reduce
import datetime

# 設定頁面與版面
st.set_page_config(page_title="Active ETF 監控系統", layout="wide")

# --- 環境路徑初始化 ---
os.chdir(os.path.dirname(os.path.abspath(__file__)))
data_dir = 'data'

if not os.path.exists(data_dir):
    st.error(f"錯誤：找不到 '{data_dir}' 資料夾，請確認 GitHub 倉庫內包含此資料夾。")
    st.stop()

# 獲取並檢查檔案
files = sorted([f for f in os.listdir(data_dir) if f.endswith('.csv') and '_' in f], reverse=True)
if not files:
    st.warning("data 資料夾為空或無符合格式檔案，請確認 GitHub Actions 是否已成功推送資料。")
    st.stop()

etf_list = sorted(list(set([f.split('_')[0] for f in files])))

# 定義 ETF 中文對應表
etf_names = {
    "00403A": "00403A 主動統一升級50",
    "00980A": "00980A 主動野村臺灣優選",
    "00981A": "00981A 主動統一台股增長",
    "00982A": "00982A 主動群益台灣強棒",
    "00992A": "00992A 主動群益科技創新"
}

st.sidebar.title("ETF 監控中心")
mode = st.sidebar.radio("分析模式", ["單檔 ETF 分析", "多檔市場分析"])

# --- 單檔 ETF 分析 ---
if mode == "單檔 ETF 分析":
    display_list = [etf_names.get(e, e) for e in etf_list]
    selected_display = st.sidebar.selectbox("選擇主動式 ETF", display_list)
    selected_etf = [k for k, v in etf_names.items() if v == selected_display][0]
    etf_files = sorted([f for f in files if f.startswith(selected_etf)], reverse=True)
    
    if etf_files:
        file_path = os.path.join(data_dir, etf_files[0])
        # CSV 資料更新時間
        m_time = pd.Timestamp(os.path.getmtime(file_path), unit='s').strftime('%Y-%m-%d')
        # 行情即時日期
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        
        df_now = pd.read_csv(file_path, encoding='utf-8-sig')
        
        st.title(f"📊 {selected_display} 分析儀表板")
        tab1, tab2, tab3 = st.tabs(["📈 ETF 行情分析", "📋 成分股分析", "🔄 持股增減分析"])
        
        with tab1:
            st.caption(f"🕒 行情日期: {today_str} (即時)")
            period_map = {"1個月": "1mo", "3個月": "3mo", "6個月": "6mo", "1年": "1y"}
            selected_period = st.radio("選擇觀察區間", list(period_map.keys()), horizontal=True)
            hist = yf.Ticker(f"{selected_etf}.TW").history(period=period_map[selected_period])
            if not hist.empty:
                last, prev = hist.iloc[-1], hist.iloc[-2]
                change = last['Close'] - prev['Close']
                pct = (change / prev['Close']) * 100
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("目前股價", f"{last['Close']:.2f}")
                c2.metric("漲跌價", f"{change:.2f}", delta=f"{change:.2f}", delta_color="normal" if change >= 0 else "inverse")
                c3.metric("漲跌幅", f"{pct:.2f}%", delta=f"{pct:.2f}%", delta_color="normal" if pct >= 0 else "inverse")
                c4.metric("成交量", f"{int(last['Volume']):,}")
                st.plotly_chart(px.line(hist, y='Close', title=f'近 {selected_period} 走勢'), use_container_width=True)
            
        with tab2:
            st.caption(f"🕒 資料更新時間: {m_time}")
            top_holdings = df_now.nlargest(20, '投資比例(%)')
            fig = px.bar(top_holdings, x='投資比例(%)', y='個股名稱', orientation='h', title="成分股權重前 20 大分佈", color='投資比例(%)', color_continuous_scale='Blues')
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
            df_display = df_now.drop(columns=['ticker'], errors='ignore')
            if '今日漲跌價' in df_display.columns: df_display['今日漲跌價'] = df_display['今日漲跌價'].apply(lambda x: f"{x:.2f}")
            st.dataframe(df_display, use_container_width=True)
            
        with tab3:
            st.caption(f"🕒 資料更新時間: {m_time}")
            if len(etf_files) >= 2:
                df_pre = pd.read_csv(os.path.join(data_dir, etf_files[1]), encoding='utf-8-sig')
                df_now['個股名稱'] = df_now['個股名稱'].astype(str).str.strip()
                df_pre['個股名稱'] = df_pre['個股名稱'].astype(str).str.strip()
                m = pd.merge(df_now, df_pre, on='個股名稱', how='outer', suffixes=('_now', '_pre')).fillna(0)
                m['股數變動'] = (m['持有股數_now'] - m['持有股數_pre']) / 1000
                cols = st.columns(4)
                status_map = {"新增": (m['持有股數_pre'] == 0) & (m['持有股數_now'] > 0), "加碼": (m['持有股數_pre'] > 0) & (m['股數變動'] > 0), "減碼": (m['持有股數_pre'] > 0) & (m['股數變動'] < 0) & (m['持有股數_now'] > 0), "出清": (m['持有股數_pre'] > 0) & (m['持有股數_now'] == 0)}
                for i, (status, mask) in enumerate(status_map.items()):
                    cols[i].subheader(status)
                    sub_df = m[mask][['個股名稱', '股數變動']].sort_values('股數變動', ascending=(status == '減碼'))
                    cols[i].dataframe(sub_df, use_container_width=True, hide_index=True)
            else: st.warning("需要至少兩份歷史資料。")

# --- 多檔市場分析 ---
else:
    # 統一基準時間
    m_time_all = pd.Timestamp(os.path.getmtime(os.path.join(data_dir, files[0])), unit='s').strftime('%Y-%m-%d')
    st.title("🌐 多檔市場綜合分析")
    sub1, sub2, sub3 = st.tabs(["📈 績效分析", "🔄 共同調倉", "🤝 共同持股"])
    with sub1:
        st.caption(f"🕒 資料更新時間: {m_time_all}")
        perf_data = []
        for etf in etf_list:
            hist = yf.Ticker(f"{etf}.TW").history(period="6mo")
            row = {'ETF': etf}
            for label, days in {"1週":5, "1個月":22, "3個月":66, "6個月":132}.items():
                if len(hist) > days:
                    curr, past = hist['Close'].iloc[-1], hist['Close'].iloc[-days]
                    row[label] = f"{((curr - past) / past) * 100:.2f}%"
                else: row[label] = "N/A"
            perf_data.append(row)
        st.table(pd.DataFrame(perf_data).set_index('ETF'))
    with sub2:
        st.caption(f"🕒 資料更新時間: {m_time_all}")
        all_changes = []
        for etf in etf_list:
            f_list = sorted([f for f in files if f.startswith(etf)], reverse=True)
            if len(f_list) >= 2:
                d_n, d_p = pd.read_csv(os.path.join(data_dir, f_list[0])), pd.read_csv(os.path.join(data_dir, f_list[1]))
                m = pd.merge(d_n, d_p, on='個股名稱', suffixes=('_n', '_p'))
                m['變動'] = (m['持有股數_n'] - m['持有股數_p']) / 1000
                m['ETF'] = etf
                all_changes.append(m[['個股名稱', '變動', 'ETF']])
        if all_changes:
            df_all = pd.concat(all_changes)
            c1, c2 = st.columns(2)
            c1.write("📈 同步買進"); c1.dataframe(df_all[df_all['變動'] > 0].groupby('個股名稱').filter(lambda x: len(x) >= 2))
            c2.write("📉 同步賣出"); c2.dataframe(df_all[df_all['變動'] < 0].groupby('個股名稱').filter(lambda x: len(x) >= 2))
    with sub3:
        st.caption(f"🕒 資料更新時間: {m_time_all}")
        dfs = []
        for etf in etf_list:
            f_latest = [f for f in files if f.startswith(etf)][0]
            df = pd.read_csv(os.path.join(data_dir, f_latest), encoding='utf-8-sig')
            df['個股名稱'] = df['個股名稱'].astype(str).str.strip()
            df['投資比例(%)'] = pd.to_numeric(df['投資比例(%)'], errors='coerce').fillna(0)
            df = df[['個股名稱', '投資比例(%)']]
            df.columns = ['個股名稱', etf]
            dfs.append(df)
        if dfs:
            df_all = reduce(lambda left, right: pd.merge(left, right, on='個股名稱', how='outer'), dfs).fillna(0)
            etf_cols = [c for c in df_all.columns if c != '個股名稱']
            count = (df_all[etf_cols] > 0).sum(axis=1)
            st.info("💡 **標記說明：** 表格最左側標記「★」者，代表該標的在涉及的所有 ETF 中，持股比例皆大於 1.00% (核心強勢股)。")
            def display_table(df_subset, title):
                st.subheader(title)
                if df_subset.empty: return
                df_disp = df_subset.copy()
                df_disp['標記'] = df_subset.apply(lambda row: "★" if all(row[col] > 1.0 for col in etf_cols) else "", axis=1)
                for col in etf_cols: df_disp[col] = df_subset[col].apply(lambda x: f"{x:.2f}")
                st.dataframe(df_disp[['標記', '個股名稱'] + etf_cols], use_container_width=True)
            display_table(df_all[count == 5], "五家 ETF 共同持有之個股權重")
            display_table(df_all[count == 4], "四家 ETF 共同持有之個股權重")
