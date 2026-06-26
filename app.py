import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from functools import reduce
import datetime

# --- 頁面初始配置 ---
st.set_page_config(page_title="Active ETF 監控系統", layout="wide")

# --- CSS 注入 (精準控制指定框線與隱藏數字編號) ---
st.markdown("""
    <style>
    /* 全域暗色系底色 */
    .stApp { background-color: #0f172a !important; color: #f8fafc !important; }
    h1, h2, h3, h4, h5, h6, p, span, label { color: #f8fafc !important; }
    
    /* 讓大盤行情等常規水平欄位文字與按鈕垂直置中對齊 */
    div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
    }
    
    /* 【核心修正】強制讓並排欄位容器（調倉、增減分析）內部所有子元件絕對靠頂端對齊，消除高低差 */
    div[data-testid="stColumn"] {
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        vertical-align: top !important;
    }
    
    /* 徹底移除 Streamlit 內部多餘的原生粗灰線 */
    hr, .stDeployButton, [data-testid="stCheckbox"] { display: none !important; }
    
    /* 專屬精美細線框框樣式 */
    .custom-notice-box {
        border: 1px solid #334155 !important;
        padding: 12px 16px !important;
        border-radius: 8px !important;
        margin-bottom: 15px !important;
        background-color: #1e293b !important;
        font-size: 14px !important;
        color: #f8fafc !important;
    }
    
    /* 調倉面板與單檔增減分析專用：加大版置頂標題，拔除所有上下Margin */
    .alignment-title-large {
        margin: 0px 0px 16px 0px !important;
        padding: 0px !important;
        font-size: 24px !important;
        font-weight: 700 !important;
        color: #f8fafc !important;
        line-height: 1.2 !important;
        display: block !important;
        min-height: 32px !important;
    }
    
    /* 【新增】固定高度面板容器：讓調倉榜（同步加碼/減碼）左右兩欄高度永遠一致，內容過多時內部自行捲動 */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #1e293b !important;
        border-color: #334155 !important;
    }
    
    /* 藍色TradingView風格按鈕文字 */
    div.stButton > button {
        background: transparent !important;
        border: none !important;
        color: #38bdf8 !important;
        text-align: left !important;
        padding: 0 !important;
        margin: 0 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }
    div.stButton > button:hover { color: #7dd3fc !important; text-decoration: underline !important; }
    
    /* 紅漲綠跌與一般文字 */
    .text-up { color: #ef4444 !important; font-weight: bold; font-size: 15px; }
    .text-down { color: #22c55e !important; font-weight: bold; font-size: 15px; }
    .text-stable { color: #94a3b8 !important; font-size: 15px; }
    .text-normal { color: #f8fafc !important; font-size: 15px; font-weight: 500; }
    </style>
""", unsafe_allow_html=True)

# --- 環境路徑初始化與靜態配置 ---
os.chdir(os.path.dirname(os.path.abspath(__file__)))
data_dir = 'data'

if not os.path.exists(data_dir):
    st.error(f"錯誤：找不到 '{data_dir}' 資料夾，請確認環境結構。")
    st.stop()

files = sorted([f for f in os.listdir(data_dir) if f.endswith('.csv') and '_' in f], reverse=True)
if not files:
    st.warning("data 資料夾為空或無符合格式檔案，請確認資料來源。")
    st.stop()

# 精確的 19 檔規模排行順序
scale_order = [
    "00981A", "00403A", "00991A", "00982A", "00992A", "00405A", "00400A", 
    "00980A", "00999A", "00993A", "00985A", "00984A", "00406A", "00995A", 
    "00994A", "00996A", "00401A", "00404A", "00987A"
]
raw_etf_list = list(set([f.split('_')[0] for f in files]))
etf_list = sorted([e for e in raw_etf_list if e in scale_order], key=lambda x: scale_order.index(x))

etf_names = {
    "00981A": "00981A 主動統一台股增長", "00403A": "00403A 主動統一升級50", "00991A": "00991A 主動復華未來50",
    "00982A": "00982A 主動群益台灣強棒", "00992A": "00992A 主動群益科技創新", "00405A": "00405A 主動富邦台灣龍耀",
    "00400A": "00400A 主動國泰動能高息", "00980A": "00980A 主動野村臺灣優選", "00999A": "00999A 主動野村臺灣高息",
    "00993A": "00993A 主動安聯台灣", "00985A": "00985A 主動野村台灣50", "00984A": "00984A 主動安聯台灣高息",
    "00406A": "00406A 主動中信台灣收益", "00995A": "00995A 主動中信台灣卓越", "00994A": "00994A 主動第一金台股優",
    "00996A": "00996A 主動兆豐台灣豐收", "00401A": "00401A 主動摩根台灣鑫收", "00404A": "00404A 主動聯博動能50",
    "00987A": "00987A 主動台新優勢成長"
}

def get_date_from_filename(filename):
    try:
        date_part = filename.split('_')[1].replace('.csv', '')
        return f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
    except:
        return "未知日期"

# 取得最新的資料時間
m_time_global = get_date_from_filename(files[0]) if files else "未知日期"
# 動態抓取今日系統日期
today_str = datetime.date.today().strftime('%Y-%m-%d')

# --- 初始化 Session State 狀態機 ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "📈 主動式 ETF 行情大盤"
if "selected_etf" not in st.session_state:
    st.session_state.selected_etf = etf_list[0] if etf_list else ""
if "sort_col" not in st.session_state:
    st.session_state.sort_col = "漲跌幅"  
if "sort_desc" not in st.session_state:
    st.session_state.sort_desc = 1  

# 側邊欄導航 (純按鈕)
st.sidebar.title("ETF 監控中心")
if st.sidebar.button("📈 返回行情大盤看板", use_container_width=True):
    st.session_state.current_page = "📈 主動式 ETF 行情大盤"
    st.rerun()

if st.sidebar.button("🌐 進入多檔綜合分析", use_container_width=True):
    st.session_state.current_page = "🌐 多檔市場綜合分析"
    st.rerun()


# ==========================================
# 模組化功能 1: 原始 Yahoo Finance 歷史行情加載
# ==========================================
@st.cache_data(ttl=60)
def load_price_data(etf_code, period="2d"):
    try:
        ticker = yf.Ticker(f"{etf_code}.TW")
        hist = ticker.history(period=period)
        return hist
    except:
        return pd.DataFrame()


# ==========================================
# 模組化功能 2: 行情基本資料集建構
# ==========================================
def build_overview_data(etf_codes):
    overview_data = []
    for etf in etf_codes:
        hist = load_price_data(etf, period="2d")
        etf_display_name = etf_names.get(etf, etf)
        row = {"代碼": etf, "ETF名稱": etf_display_name, "最新價": 0.0, "漲跌價": 0.0, "漲跌幅": 0.0, "成交量": 0}
        if len(hist) >= 2:
            last = hist.iloc[-1]
            prev = hist.iloc[-2]
            change = last['Close'] - prev['Close']
            pct = (change / prev['Close']) * 100
            row["最新價"] = round(last['Close'], 2)
            row["漲跌價"] = round(change, 2)
            row["漲跌幅"] = round(pct, 2)
            row["成交量"] = int(last['Volume'])
        elif len(hist) == 1:
            last = hist.iloc[-1]
            row["最新價"] = round(last['Close'], 2)
        overview_data.append(row)
    return overview_data


# ==========================================
# 主頁面 1: 行情大盤看板
# ==========================================
def render_home_page(overview_list):
    st.title("🏆 台灣主動式 ETF 即時行情大盤")
    st.write(f"資料更新時間：{today_str}")
    
    # 主頁專屬框框提示說明
    st.markdown("""
        <div class="custom-notice-box">
            💡 <strong>使用提示：</strong>點選下方表格清單中的 <strong>ETF名稱</strong> 藍色連結，即可自由進入切換查看該檔 ETF 的「完整成分股明細」與「持股增減異動」。
        </div>
    """, unsafe_allow_html=True)
    
    total_etfs = len(overview_list)
    up_count = sum(1 for x in overview_list if x["漲跌價"] > 0)
    down_count = sum(1 for x in overview_list if x["漲跌價"] < 0)
    avg_pct = sum(x["漲跌幅"] for x in overview_list) / total_etfs if total_etfs > 0 else 0.0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("ETF 總數", f"{total_etfs} 檔")
    m2.metric("上漲家數", f"▲ {up_count} 家")
    m3.metric("下跌家數", f"▼ {down_count} 家")
    m4.metric("平均漲跌幅", f"{avg_pct:+.2f}%")
    
    search_query = st.text_input("🔍 輸入 ETF 代碼或名稱進行即時篩選：", "").strip().lower()
    filtered_list = overview_list
    if search_query:
        filtered_list = [x for x in overview_list if search_query in x["代碼"].lower() or search_query in x["ETF名稱"].lower()]
    
    # 建立行情標頭行
    st.markdown("<div style='padding: 0px 20px; margin-bottom: 5px;'>", unsafe_allow_html=True)
    h_c1, h_c2, h_c3, h_c4, h_c5, h_c6 = st.columns([1, 3.5, 1.5, 1.5, 1.5, 1.5])
    
    header_mapping = {"代碼": h_c1, "ETF名稱": h_c2, "最新價": h_c3, "漲跌價": h_c4, "漲跌幅": h_c5, "成交量": h_c6}
    for label, col_obj in header_mapping.items():
        with col_obj:
            sort_suffix = " ⇅"
            if st.session_state.sort_col == label:
                if st.session_state.sort_desc == 1: sort_suffix = " ⬇"
                elif st.session_state.sort_desc == 2: sort_suffix = " ⬆"
            
            if st.button(f"{label}{sort_suffix}", key=f"btn_sort_{label}"):
                if st.session_state.sort_col == label:
                    st.session_state.sort_desc = (st.session_state.sort_desc + 1) % 3
                else:
                    st.session_state.sort_col = label
                    st.session_state.sort_desc = 1  
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
    
    if st.session_state.sort_desc == 1:
        filtered_list = sorted(filtered_list, key=lambda x: x[st.session_state.sort_col], reverse=True)
    elif st.session_state.sort_desc == 2:
        filtered_list = sorted(filtered_list, key=lambda x: x[st.session_state.sort_col], reverse=False)
        
    for row in filtered_list:
        c1, c2, c3, c4, c5, c6 = st.columns([1, 3.5, 1.5, 1.5, 1.5, 1.5])
        with c1: st.markdown(f"<span class='text-normal'>{row['代碼']}</span>", unsafe_allow_html=True)
        with c2:
            if st.button(row["ETF名稱"], key=f"click_{row['代碼']}", use_container_width=True):
                st.session_state.selected_etf = row["代碼"]
                st.session_state.current_page = "📊 單檔詳細分析"
                st.rerun()
        with c3: st.markdown(f"<span class='text-normal'>{row['最新價']:.2f}</span>", unsafe_allow_html=True)
            
        if row["漲跌價"] > 0:
            c4.markdown(f"<span class='text-up'>+{row['漲跌價']:.2f}</span>", unsafe_allow_html=True)
            c5.markdown(f"<span class='text-up'>+{row['漲跌幅']:.2f}%</span>", unsafe_allow_html=True)
        elif row["漲跌價"] < 0:
            c4.markdown(f"<span class='text-down'>{row['漲跌價']:.2f}</span>", unsafe_allow_html=True)
            c5.markdown(f"<span class='text-down'>{row['漲跌幅']:.2f}%</span>", unsafe_allow_html=True)
        else:
            c4.markdown("<span class='text-stable'>0.00</span>", unsafe_allow_html=True)
            c5.markdown("<span class='text-stable'>0.00%</span>", unsafe_allow_html=True)
            
        with c6: st.markdown(f"<span class='text-normal'>{row['成交量']:,}</span>", unsafe_allow_html=True)


# ==========================================
# 主頁面 2: 單檔詳細分析頁面
# ==========================================
def render_single_etf():
    display_list = [etf_names.get(e, e) for e in etf_list]
    try: current_idx = etf_list.index(st.session_state.selected_etf)
    except: current_idx = 0
        
    selected_display = st.sidebar.selectbox("切換觀察其他主動式 ETF", display_list, index=current_idx)
    selected_etf = [k for k, v in etf_names.items() if v == selected_display][0]
    st.session_state.selected_etf = selected_etf
    
    etf_files = sorted([f for f in files if f.startswith(selected_etf)], reverse=True)
    if etf_files:
        m_time = get_date_from_filename(etf_files[0])
        df_now = pd.read_csv(os.path.join(data_dir, etf_files[0]), encoding='utf-8-sig')
        
        st.title(f"📊 {selected_display} 分析儀表板")
        if st.button("← 返回即時行情大盤", type="primary"):
            st.session_state.current_page = "📈 主動式 ETF 行情大盤"
            st.rerun()
            
        tab1, tab2, tab3 = st.tabs(["📈 ETF 行情分析", "📋 成分股分析", "🔄 持股增減分析"])
        
        with tab1:
            st.write(f"資料更新時間：{today_str}")
            period_map = {"1個月": "1mo", "3個月": "3mo", "6個月": "6mo", "1年": "1y"}
            selected_period = st.radio("選擇觀察區間", list(period_map.keys()), horizontal=True)
            
            hist = load_price_data(selected_etf, period=period_map[selected_period])
            if not hist.empty:
                last, prev = hist.iloc[-1], hist.iloc[-2] if len(hist) > 1 else hist.iloc[-1]
                change = last['Close'] - prev['Close']
                pct = (change / prev['Close']) * 100
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("目前股價", f"{last['Close']:.2f}")
                c2.metric("漲跌價", f"{change:.2f}", delta=f"{change:.2f}", delta_color="normal" if change >= 0 else "inverse")
                c3.metric("漲跌幅", f"{pct:.2f}%", delta=f"{pct:.2f}%", delta_color="normal" if pct >= 0 else "inverse")
                c4.metric("成交量(股)", f"{int(last['Volume'] if 'Volume' in last else 0):,}")
                
                fig_k = go.Figure(data=[go.Candlestick(
                    x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'],
                    increasing_line_color='#ef4444', decreasing_line_color='#22c55e'
                )])
                fig_k.update_layout(title=f'近 {selected_period} 技術 K 線圖走勢', template='plotly_dark', xaxis_rangeslider_visible=False)
                st.plotly_chart(fig_k, use_container_width=True)
                
        with tab2:
            st.write(f"資料更新時間：{m_time}")
            top_holdings = df_now.nlargest(10, '投資比例(%)')
            fig = px.bar(top_holdings, x='投資比例(%)', y='個股名稱', orientation='h', title="成分股權重前 10 大分佈", color='投資比例(%)', color_continuous_scale='Blues')
            fig.update_layout(yaxis={'categoryorder': 'total ascending'}, template='plotly_dark')
            st.plotly_chart(fig, use_container_width=True)
            
            target_cols = ['個股名稱', '持有股數', '投資比例(%)']
            display_cols = [c for c in target_cols if c in df_now.columns]
            st.dataframe(df_now[display_cols].copy(), use_container_width=True, hide_index=True)
            
        with tab3:
            st.write(f"資料更新時間：{m_time}")
            if len(etf_files) >= 2:
                df_pre = pd.read_csv(os.path.join(data_dir, etf_files[1]), encoding='utf-8-sig')
                
                df_now['個股名稱'] = df_now['個股名稱'].astype(str).str.strip()
                df_pre['個股名稱'] = df_pre['個股名稱'].astype(str).str.strip()
                
                df_now['持有股數'] = pd.to_numeric(df_now['持有股數'], errors='coerce').fillna(0.0)
                df_pre['持有股數'] = pd.to_numeric(df_pre['持有股數'], errors='coerce').fillna(0.0)
                
                m = pd.merge(df_now, df_pre, on='個股名稱', how='outer', suffixes=('_now', '_pre')).fillna(0.0)
                m['張數變動'] = (m['持有股數_now'] - m['持有股數_pre']) / 1000.0
                
                status_map = {
                    "🚀 新增持股": (m['持有股數_pre'] == 0) & (m['持有股數_now'] > 0), 
                    "🔥 操盤加碼": (m['持有股數_pre'] > 0) & (m['張數變動'] > 0), 
                    "⚡ 機構減碼": (m['持有股數_pre'] > 0) & (m['張數變動'] < 0) & (m['持有股數_now'] > 0), 
                    "❌ 全額出清": (m['持有股數_pre'] > 0) & (m['持有股數_now'] == 0)
                }
                
                # 【修正】固定四個面板的表格高度，避免因各分類股票筆數不同造成欄位高度不一致
                HOLDING_PANEL_HEIGHT = 380
                
                cols = st.columns(4)
                for i, (status, mask) in enumerate(status_map.items()):
                    with cols[i]:
                        # 【優化】棄用 st.subheader，改用完全沒有Margin外距的自訂 HTML 置頂加大標題
                        st.markdown(f'<div class="alignment-title-large">{status}</div>', unsafe_allow_html=True)
                        sub_df = m[mask][['個股名稱', '張數變動']].copy()
                        sub_df = sub_df.sort_values('張數變動', ascending=(i == 2 or i == 3))
                        sub_df['張數變動'] = sub_df['張數變動'].map('{:,.2f}'.format)
                        st.dataframe(
                            sub_df,
                            use_container_width=True,
                            hide_index=True,
                            height=HOLDING_PANEL_HEIGHT
                        )


# ==========================================
# 主頁面 3: 多檔市場綜合分析
# ==========================================
def render_market_analysis():
    st.title("🌐 多檔市場綜合分析面板")
    sub1, sub2, sub3 = st.tabs(["📈 跨週期績效分析", "🔄 共同調倉共振分析", "🤝 投信全方位共同持股總表"])
    
    with sub1:
        st.write(f"資料更新時間：{today_str}")
        st.markdown("""
            <div class="custom-notice-box">
                💡 <strong>嚴格區間對比提示：</strong> 系統已自動加入 <strong>0050 元大台灣50</strong> 作為市場基準線（Benchmark）。<br>
                ⚠️ <strong>存活過濾機制：</strong>為確保對比公平性，<strong>若 ETF 上市時間未滿所選區間，將自動隱藏不予評比</strong>，避免剛上市新股造成數據失真。
            </div>
        """, unsafe_allow_html=True)
        
        perf_data = []
        # 定義每個區間「理論上最少需要具備的交易日天數」（扣除例假日，保守估計）
        min_days_map = {"1週": 4, "1個月": 15, "3個月": 50, "6個月": 100}
        period_map = {"1週": "7d", "1個月": "1mo", "3個月": "3mo", "6個月": "6mo"}
        chart_period = st.radio("選擇圖表對比區間", list(period_map.keys()), horizontal=True, key="analysis_perf_period")
        
        # 1. 先抓取 0050 作為大盤基準線
        df_0050 = load_price_data("0050", period=period_map[chart_period])
        benchmark_perf = 0.0
        if not df_0050.empty and len(df_0050) >= 2:
            first_b = df_0050['Close'].iloc[0]
            last_b = df_0050['Close'].iloc[-1]
            benchmark_perf = round(((last_b - first_b) / first_b) * 100, 2)
            
        # 將大盤放進資料清單中
        perf_data.append({'ETF': "📌 0050 元大台灣50 (大盤)", '績效(%)': benchmark_perf, '類型': '大盤基準'})
        
        # 2. 抓取其餘主動式 ETF 的績效（加入嚴格天數過濾）
        required_min_days = min_days_map[chart_period]
        
        for etf in etf_list:
            hist = load_price_data(etf, period=period_map[chart_period])
            
            # 【核心邏輯】：如果這檔 ETF 回傳的歷史 K 線天數小於要求的天數，代表它在這個區間根本還沒上市或資料不足，直接跳過！
            if hist.empty or len(hist) < required_min_days:
                continue
                
            etf_display_name = etf_names.get(etf, etf)
            row = {'ETF': etf_display_name, '績效(%)': 0.0, '類型': '主動式 ETF'}
            
            first_p = hist['Close'].iloc[0]
            last_p = hist['Close'].iloc[-1]
            row['績效(%)'] = round(((last_p - first_p) / first_p) * 100, 2)
            perf_data.append(row)
            
        df_perf = pd.DataFrame(perf_data)
        
        # 如果除了大盤以外，沒有任何主動式 ETF 滿足這個時間條件
        if len(df_perf) <= 1:
            st.warning(f"目前沒有任何主動式 ETF 的上市時間滿足「{chart_period}」的要求。")
        else:
            # 依據績效由高到低排序
            df_plot = df_perf.sort_values('績效(%)', ascending=False)
            
            # 繪製長條圖
            fig_perf = px.bar(
                df_plot, 
                x='ETF', 
                y='績效(%)', 
                text='績效(%)', 
                color='類型',
                color_discrete_map={"大盤基準": "#f59e0b", "主動式 ETF": "#38bdf8"},
                title=f"近 {chart_period} 累積績效 vs 0050 大盤對比 (已過濾剛上市不符資格者)"
            )
            
            # 在圖中加上一條水平虛線穿過 0050
            fig_perf.add_hline(
                y=benchmark_perf, 
                line_dash="dash", 
                line_color="#f59e0b", 
                annotation_text=f" 0050 大盤線 ({benchmark_perf:+.2f}%)", 
                annotation_position="top left"
            )
            
            fig_perf.update_traces(texttemplate='%{text}%', textposition='outside')
            fig_perf.update_layout(xaxis_tickangle=-45, yaxis=dict(ticksuffix="%"), height=550, template='plotly_dark')
            st.plotly_chart(fig_perf, use_container_width=True)
            
            # 數據表計算超額報酬
            df_table = df_plot.copy()
            df_table['領先大盤(%)'] = df_table['績效(%)'] - benchmark_perf
            df_table['領先大盤(%)'] = df_table['領先大盤(%)'].apply(lambda x: f"{x:+.2f}%" if x != 0 else "-")
            df_table['績效(%)'] = df_table['績效(%)'].apply(lambda x: f"{x:+.2f}%")
            
            st.dataframe(df_table.set_index('ETF')[['類型', '績效(%)', '領先大盤(%)']], use_container_width=True)
    with sub2:
        st.write(f"資料更新時間：{m_time_global}")
        all_changes = []
        for etf in etf_list:
            f_list = sorted([f for f in files if f.startswith(etf)], reverse=True)
            if len(f_list) >= 2:
                d_n = pd.read_csv(os.path.join(data_dir, f_list[0]))
                d_p = pd.read_csv(os.path.join(data_dir, f_list[1]))
                m = pd.merge(d_n, d_p, on='個股名稱', suffixes=('_n', '_p'))
                m['變動'] = (m['持有股數_n'] - m['持有股數_p']) / 1000
                m['ETF'] = etf
                all_changes.append(m[['個股名稱', '變動', 'ETF']])
                
        if all_changes:
            df_all = pd.concat(all_changes)
            c1, c2 = st.columns(2)
            buy_raw = df_all[df_all['變動'] > 0]
            sell_raw = df_all[df_all['變動'] < 0]
            
            # 【修正】固定左右兩欄調倉榜的面板高度，內容過多時改為內部自行捲動，避免兩欄高度不一致
            SYNC_PANEL_HEIGHT = 480
            
            with c1:
                # 【優化】利用 HTML 置頂大標題，配合全域 Column CSS 達到絕對水平齊頭
                st.markdown('<div class="alignment-title-large">📈 同步加碼</div>', unsafe_allow_html=True)
                buy_grouped = buy_raw.groupby('個股名稱').size().reset_index(name='涉及ETF數量')
                buy_grouped = buy_grouped[buy_grouped['涉及ETF數量'] >= 2].sort_values('涉及ETF數量', ascending=False)
                with st.container(height=SYNC_PANEL_HEIGHT, border=True):
                    if not buy_grouped.empty:
                        for _, b_row in buy_grouped.iterrows():
                            stock_name = b_row['個股名稱']
                            with st.expander(f"{stock_name} ({b_row['涉及ETF數量']}家)"):
                                for _, d_row in buy_raw[buy_raw['個股名稱'] == stock_name].iterrows():
                                    st.write(f"🔹 {d_row['ETF']} : `+{d_row['變動']:.2f} 張`")
                    else:
                        st.write("目前無符合 2 家以上同步買進的標的。")

            with c2:
                st.markdown('<div class="alignment-title-large">📉 同步減碼</div>', unsafe_allow_html=True)
                sell_grouped = sell_raw.groupby('個股名稱').size().reset_index(name='涉及ETF數量')
                sell_grouped = sell_grouped[sell_grouped['涉及ETF數量'] >= 2].sort_values('涉及ETF數量', ascending=False)
                with st.container(height=SYNC_PANEL_HEIGHT, border=True):
                    if not sell_grouped.empty:
                        for _, s_row in sell_grouped.iterrows():
                            stock_name = s_row['個股名稱']
                            with st.expander(f"{stock_name} ({s_row['涉及ETF數量']}家)"):
                                for _, d_row in sell_raw[sell_raw['個股名稱'] == stock_name].iterrows():
                                    st.write(f"🔸 {d_row['ETF']} : `{d_row['變動']:.2f} 張`")
                    else:
                        st.write("目前無符合 2 家以上同步減碼的標的。")

    with sub3:
        st.write(f"資料更新時間：{m_time_global}")
        
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
            df_total = reduce(lambda left, right: pd.merge(left, right, on='個股名稱', how='outer'), dfs).fillna(0)
            etf_cols = [c for c in df_total.columns if c != '個股名稱']
            
            df_total['持有投信數'] = (df_total[etf_cols] > 0).sum(axis=1)
            df_total['核心標記'] = df_total.apply(lambda r: "★" if all(r[col] > 1.0 for col in etf_cols if r[col] > 0) else "", axis=1)
            
            for col in etf_cols:
                df_total[col] = df_total[col].apply(lambda x: f"{x:.2f}%" if x > 0 else "-")
                
            view_cols = ['核心標記', '持有投信數', '個股名稱'] + etf_cols
            df_disp = df_total[view_cols].sort_values('持有投信數', ascending=False)
            
            st.subheader("📋 主動式投信機構共同持股萬用總表")
            
            # 修正：加入共同持股總表的精美細線框框樣式
            st.markdown("""
                <div class="custom-notice-box">
                    📝 <strong>【標記說明】</strong> ★ 核心標記：代表該股票在所有買進它的主動式 ETF 中持股皆大於 1.00% ｜ 持有投信數：代表該股票被多少家主動式 ETF 納入成分股
                </div>
            """, unsafe_allow_html=True)
            
            st.dataframe(df_disp, use_container_width=True, hide_index=True)


# ==========================================
# 終端路由主渲染控制器
# ==========================================
if st.session_state.current_page == "📈 主動式 ETF 行情大盤":
    raw_market_list = build_overview_data(etf_list)
    render_home_page(raw_market_list)
elif st.session_state.current_page == "📊 單檔詳細分析":
    render_single_etf()
else:
    render_market_analysis()
