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

# --- 定義精確的 19 檔規模排行順序 ---
scale_order = [
    "00981A", "00403A", "00991A", "00982A", "00992A", "00405A", "00400A", 
    "00980A", "00999A", "00993A", "00985A", "00984A", "00406A", "00995A", 
    "00994A", "00996A", "00401A", "00404A", "00987A"
]

# 讀取資料夾內的 ETF，並嚴格依照上方規模順序排序
raw_etf_list = list(set([f.split('_')[0] for f in files]))
etf_list = sorted([e for e in raw_etf_list if e in scale_order], key=lambda x: scale_order.index(x))

# 定義這 19 檔的精簡版中文對應名稱
etf_names = {
    "00981A": "00981A 主動統一台股增長",
    "00403A": "00403A 主動統一升級50",
    "00991A": "00991A 主動復華未來50",
    "00982A": "00982A 主動群益台灣強棒",
    "00992A": "00992A 主動群益科技創新",
    "00405A": "00405A 主動富邦台灣龍耀",
    "00400A": "00400A 主動國泰動能高息",
    "00980A": "00980A 主動野村臺灣優選",
    "00999A": "00999A 主動野村臺灣高息",
    "00993A": "00993A 主動安聯台灣",
    "00985A": "00985A 主動野村台灣50",
    "00984A": "00984A 主動安聯台灣高息",
    "00406A": "00406A 主動中信台灣收益",
    "00995A": "00995A 主動中信台灣卓越",
    "00994A": "00994A 主動第一金台股優",
    "00996A": "00996A 主動兆豐台灣豐收",
    "00401A": "00401A 主動摩根台灣鑫收",
    "00404A": "00404A 主動聯博動能50",
    "00987A": "00987A 主動台新優勢成長"
}

# 輔助函式：從檔名提取日期
def get_date_from_filename(filename):
    try:
        date_part = filename.split('_')[1].replace('.csv', '')
        return f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
    except:
        return "未知日期"

# --- 初始化 Session State ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "📈 主動式 ETF 行情大盤"
if "selected_etf" not in st.session_state:
    st.session_state.selected_etf = etf_list[0]

# 側邊欄導覽 (使用按鈕形式，避免 Radio 搶狀態造成的跳轉失效)
st.sidebar.title("ETF 監控中心")
st.sidebar.markdown(f"**目前位置**: {st.session_state.current_page}")
st.sidebar.divider()

if st.sidebar.button("📈 返回行情大盤看板", use_container_width=True):
    st.session_state.current_page = "📈 主動式 ETF 行情大盤"
    st.rerun()

if st.sidebar.button("🌐 進入多檔綜合分析", use_container_width=True):
    st.session_state.current_page = "🌐 多檔市場綜合分析"
    st.rerun()

# --- 1. 首頁：主動式 ETF 行情大盤 ---
if st.session_state.current_page == "📈 主動式 ETF 行情大盤":
    st.title("🏆 台灣主動式 ETF 即時行情大盤")
    st.caption("數據來源：Yahoo Finance 即時串接（依資產規模由大到小排序）")
    
    overview_data = []
    with st.spinner("正在加載最新即時行情..."):
        for etf in etf_list:
            hist = yf.Ticker(f"{etf}.TW").history(period="2d")
            etf_display_name = etf_names.get(etf, etf)
            row = {
                "代碼": etf,
                "ETF 名稱": etf_display_name,
                "目前股價": 0.0,
                "漲跌價": 0.0,
                "漲跌幅(%)": 0.0,
                "成交量(張)": 0
            }
            if len(hist) >= 2:
                last = hist.iloc[-1]
                prev = hist.iloc[-2]
                change = last['Close'] - prev['Close']
                pct = (change / prev['Close']) * 100
                row["目前股價"] = round(last['Close'], 2)
                row["漲跌價"] = round(change, 2)
                row["漲跌幅(%)"] = round(pct, 2)
                row["成交量(張)"] = int(last['Volume'] / 1000)
            overview_data.append(row)
            
    df_overview = pd.DataFrame(overview_data)
    
    st.info("💡 **提示：直接點擊下方列表中的「ETF 中文名稱」，即可看該 ETF 的詳細成分股分析與持股增減！**")
    
    # 橫向欄位對齊排版（回復你覺得好看的樣式）
    h_c1, h_c2, h_c3, h_c4, h_c5, h_c6 = st.columns([1, 4, 1.5, 1.5, 1.5, 1.5])
    h_c1.markdown("**代碼**")
    h_c2.markdown("**ETF 名稱 (點擊名稱進入分析)**")
    h_c3.markdown("**目前股價**")
    h_c4.markdown("**漲跌價**")
    h_c5.markdown("**漲跌幅**")
    h_c6.markdown("**成交量(張)**")
    st.divider()
    
    for idx, row in df_overview.iterrows():
        c1, c2, c3, c4, c5, c6 = st.columns([1, 4, 1.5, 1.5, 1.5, 1.5])
        c1.write(f"**{row['代碼']}**")
        
        # 關鍵修正：將點擊事件綁定在名稱上，點擊後立刻變更 Page 狀態，並立刻 rerun 跳轉！
        if c2.button(row["ETF 名稱"], key=f"etf_click_{row['代碼']}", use_container_width=True):
            st.session_state.selected_etf = row["代碼"]
            st.session_state.current_page = "📊 單檔詳細分析"
            st.rerun()
            
        c3.text(f"{row['目前股價']:.2f}")
        
        if row["漲跌價"] > 0:
            c4.markdown(f"<span style='color:red'>+{row['漲跌價']:.2f}</span>", unsafe_allow_html=True)
            c5.markdown(f"<span style='color:red'>+{row['漲跌幅(%)']:.2f}%</span>", unsafe_allow_html=True)
        elif row["漲跌價"] < 0:
            c4.markdown(f"<span style='color:green'>{row['漲跌價']:.2f}</span>", unsafe_allow_html=True)
            c5.markdown(f"<span style='color:green'>{row['漲跌幅(%)']:.2f}%</span>", unsafe_allow_html=True)
        else:
            c4.text("0.00")
            c5.text("0.00%")
            
        c6.text(f"{row['成交量(張)']:,}")
            
# --- 2. 單檔詳細分析（點選名字後跳轉的頁面） ---
elif st.session_state.current_page == "📊 單檔詳細分析":
    display_list = [etf_names.get(e, e) for e in etf_list]
    
    try:
        current_idx = etf_list.index(st.session_state.selected_etf)
    except:
        current_idx = 0
        
    # 允許使用者在單檔分析頁面中，直接透過下拉選單切換其他 ETF
    selected_display = st.sidebar.selectbox("切換其他主動式 ETF", display_list, index=current_idx)
    selected_etf = [k for k, v in etf_names.items() if v == selected_display][0]
    st.session_state.selected_etf = selected_etf
    
    etf_files = sorted([f for f in files if f.startswith(selected_etf)], reverse=True)
    
    if etf_files:
        m_time = get_date_from_filename(etf_files[0])
        today_str = datetime.date.today().strftime('%Y-%m-%d')
        df_now = pd.read_csv(os.path.join(data_dir, etf_files[0]), encoding='utf-8-sig')
        
        st.title(f"📊 {selected_display} 分析儀表板")
        if st.button("← 返回即時行情大盤", type="primary"):
            st.session_state.current_page = "📈 主動式 ETF 行情大盤"
            st.rerun()
            
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
            top_holdings = df_now.nlargest(10, '投資比例(%)')
            fig = px.bar(top_holdings, x='投資比例(%)', y='個股名稱', orientation='h', title="成分股權重前 10 大分佈", color='投資比例(%)', color_continuous_scale='Blues')
            fig.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
            
            target_cols = ['個股名稱', '持有股數', '投資比例(%)']
            display_cols = [c for c in target_cols if c in df_now.columns]
            df_display = df_now[display_cols].copy()
            st.dataframe(df_display, use_container_width=True, hide_index=True)
            
        with tab3:
            st.caption(f"🕒 資料更新時間: {m_time}")
            if len(etf_files) >= 2:
                df_pre = pd.read_csv(os.path.join(data_dir, etf_files[1]), encoding='utf-8-sig')
                df_now['個股名稱'] = df_now['個股名稱'].astype(str).str.strip()
                df_pre['個股名稱'] = df_pre['個股名稱'].astype(str).str.strip()
                m = pd.merge(df_now, df_pre, on='個股名稱', how='outer', suffixes=('_now', '_pre')).fillna(0)
                
                m['張數變動'] = (m['持有股數_now'] - m['持有股數_pre']) / 1000
                
                cols = st.columns(4)
                status_map = {
                    "新增": (m['持有股數_pre'] == 0) & (m['持有股數_now'] > 0), 
                    "加碼": (m['持有股數_pre'] > 0) & (m['張數變動'] > 0), 
                    "減碼": (m['持有股數_pre'] > 0) & (m['張數變動'] < 0) & (m['持有股數_now'] > 0), 
                    "出清": (m['持有股數_pre'] > 0) & (m['持有股數_now'] == 0)
                }
                
                for i, (status, mask) in enumerate(status_map.items()):
                    cols[i].subheader(status)
                    sub_df = m[mask][['個股名稱', '張數變動']].sort_values('張數變動', ascending=(status == '減碼'))
                    cols[i].dataframe(sub_df, use_container_width=True, hide_index=True)
            else: st.warning("需要至少兩份歷史資料。")

# --- 3. 多檔市場分析（保留核心價值功能） ---
else:
    m_time_all = get_date_from_filename(files[0])
    st.title("🌐 多檔市場綜合分析")
    sub1, sub2, sub3 = st.tabs(["📈 績效分析", "🔄 共同調倉", "🤝 共同持股"])
    
    with sub1:
        st.caption(f"🕒 資料更新時間: {m_time_all}")
        perf_data = []
        today = pd.Timestamp.now(tz='Asia/Taipei') 
        
        intervals = {
            "1週": pd.Timedelta(days=7),
            "1個月": pd.Timedelta(days=30),
            "3個月": pd.Timedelta(days=90),
            "6個月": pd.Timedelta(days=180)
        }
        
        for etf in etf_list:
            hist = yf.Ticker(f"{etf}.TW").history(period="2y")
            etf_display_name = etf_names.get(etf, etf)
            row = {'ETF': etf_display_name}
            
            if not hist.empty:
                if hist.index.tz is None:
                    hist.index = hist.index.tz_localize('Asia/Taipei')
                curr_price = hist['Close'].iloc[-1]
                
                for label, delta in intervals.items():
                    target_date = today - delta
                    past_records = hist[hist.index <= target_date]
                    if not past_records.empty:
                        past_price = past_records['Close'].iloc[-1]
                        perf = ((curr_price - past_price) / past_price) * 100
                        row[label] = f"{perf:+.2f}%"
                    else:
                        row[label] = "資料不足"
            else:
                for label in intervals:
                    row[label] = "無數據"
            perf_data.append(row)
            
        df_perf = pd.DataFrame(perf_data)
        
        if not df_perf.empty:
            st.subheader("📊 績效對比直條圖")
            chart_period = st.radio("選擇圖表對比區間", list(intervals.keys()), horizontal=True, key="perf_chart_period")
            plot_list = []
            for r in perf_data:
                val_str = r.get(chart_period, "資料不足")
                if " %" in val_str or "%" in val_str:
                    try:
                        val_num = float(val_str.replace('%', '').replace('+', ''))
                        plot_list.append({'ETF': r['ETF'], '績效(%)': val_num})
                    except: pass
            
            if plot_list:
                df_plot = pd.DataFrame(plot_list).sort_values('績效(%)', ascending=False)
                fig_perf = px.bar(df_plot, x='ETF', y='績效(%)', text='績效(%)', title=f"各檔 ETF 近 {chart_period} 績效排序", color='績效(%)', color_continuous_scale=px.colors.diverging.RdYlGn)
                fig_perf.update_traces(texttemplate='%{text}%', textposition='outside')
                fig_perf.update_layout(xaxis_tickangle=-45, yaxis=dict(ticksuffix="%"), height=500)
                st.plotly_chart(fig_perf, use_container_width=True)
        
        st.subheader("📋 績效詳細數據表")
        st.dataframe(df_perf.set_index('ETF'), use_container_width=True)

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
            buy_df = df_all[df_all['變動'] > 0].groupby('個股名稱').filter(lambda x: len(x) >= 2)
            sell_df = df_all[df_all['變動'] < 0].groupby('個股名稱').filter(lambda x: len(x) >= 2)
            
            c1.write("📈 同步買進"); c1.dataframe(buy_df.sort_values('個股名稱'), use_container_width=True)
            c2.write("📉 同步賣出"); c2.dataframe(sell_df.sort_values('個股名稱'), use_container_width=True)

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
            df_all['持有投信數'] = count
            
            st.info("💡 **標記說明：** 表格最左側標記「★」者，代表該標的在涉及的所有 ETF 中，持股比例皆大於 1.00% (核心強勢股)。")
            
            def display_table(df_subset, title):
                st.subheader(title)
                if df_subset.empty: return
                df_disp = df_subset.copy()
                df_disp['標記'] = df_subset.apply(lambda row: "★" if all(row[col] > 1.0 for col in etf_cols if row[col] > 0) else "", axis=1)
                for col in etf_cols: df_disp[col] = df_subset[col].apply(lambda x: f"{x:.2f}")
                
                show_cols = ['標記', '個股名稱', '持有投信數'] + etf_cols
                st.dataframe(df_disp[show_cols].sort_values('持有投信數', ascending=False), use_container_width=True)
            
            max_holding_count = int(count.max())
            if max_holding_count >= 5:
                display_table(df_all[count >= 5], f"🔥 熱門核心：5 家以上投信共同持有個股 (最高共持: {max_holding_count} 家)")
                display_table(df_all[(count >= 2) & (count < 5)], "等外英雄：2 ~ 4 家投信共同持有個股")
            else:
                display_table(df_all[count >= 2], f"群英會：2 家以上投信共同持有個股 (最高共持: {max_holding_count} 家)")
