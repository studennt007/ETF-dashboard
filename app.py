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

# --- CSS 注入 ---
st.markdown("""
    <style>
    .stApp { background-color: #0f172a !important; color: #f8fafc !important; }
    h1, h2, h3, h4, h5, h6, p, span, label { color: #f8fafc !important; }
    div[data-testid="stHorizontalBlock"] { align-items: center !important; }
    div[data-testid="stColumn"] {
        display: flex !important;
        flex-direction: column !important;
        justify-content: flex-start !important;
        vertical-align: top !important;
    }
    hr, .stDeployButton, [data-testid="stCheckbox"] { display: none !important; }
    .custom-notice-box {
        border: 1px solid #334155 !important;
        padding: 12px 16px !important;
        border-radius: 8px !important;
        margin-bottom: 15px !important;
        background-color: #1e293b !important;
        font-size: 14px !important;
        color: #f8fafc !important;
    }
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
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #1e293b !important;
        border-color: #334155 !important;
    }
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

scale_order = [
    "00981A", "00403A", "00991A", "00982A", "00992A", "00400A", "00405A",
    "00407A", "00980A", "00999A", "00993A", "00985A", "00984A", "00406A",
    "00995A", "00994A", "00996A", "00404A", "00401A", "00987A"
]
raw_etf_list = list(set([f.split('_')[0] for f in files]))
etf_list = sorted([e for e in raw_etf_list if e in scale_order], key=lambda x: scale_order.index(x))

etf_names = {
    "00981A": "00981A 主動統一台股增長", "00403A": "00403A 主動統一升級50", "00991A": "00991A 主動復華未來50",
    "00982A": "00982A 主動群益台灣強棒", "00992A": "00992A 主動群益科技創新", "00405A": "00405A 主動富邦台灣龍耀",
    "00400A": "00400A 主動國泰動能高息", "00407A": "00407A 主動凱基台灣", "00980A": "00980A 主動野村臺灣優選",
    "00999A": "00999A 主動野村臺灣高息", "00993A": "00993A 主動安聯台灣", "00985A": "00985A 主動野村台灣50",
    "00984A": "00984A 主動安聯台灣高息", "00406A": "00406A 主動中信台灣收益", "00995A": "00995A 主動中信台灣卓越",
    "00994A": "00994A 主動第一金台股優", "00996A": "00996A 主動兆豐台灣豐收", "00401A": "00401A 主動摩根台灣鑫收",
    "00404A": "00404A 主動聯博動能50", "00987A": "00987A 主動台新優勢成長"
}


def get_date_from_filename(filename):
    """回傳人類可讀格式 YYYY-MM-DD，供畫面顯示用（用於持股 CSV 的資料日期）"""
    try:
        date_part = filename.split('_')[1].replace('.csv', '')
        return f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
    except:
        return "未知日期"


def get_file_date_str(filename):
    """回傳檔名中的原始日期字串 YYYYMMDD，供排序/比較用"""
    try:
        return filename.split('_')[1].replace('.csv', '')
    except:
        return "00000000"


def pick_baseline_file(etf_files_sorted_desc, period_days=None, custom_date_str=None):
    """
    etf_files_sorted_desc: 該 ETF 由新到舊排序的檔名 list (index 0 為最新)
    period_days: 1/5/10/20，表示往回數第幾份資料(交易日)
    custom_date_str: 'YYYYMMDD'，表示找『小於等於此日期』中最新的一份資料
    回傳挑選到的基準檔名字串，找不到則回傳 None
    """
    if custom_date_str:
        candidates = [f for f in etf_files_sorted_desc if get_file_date_str(f) <= custom_date_str]
        return candidates[0] if candidates else None
    if period_days is not None and period_days < len(etf_files_sorted_desc):
        return etf_files_sorted_desc[period_days]
    return None


def render_period_selector(key_prefix, available_date_strs):
    """畫出『1天/5天/10天/20天/自訂日期』選擇器，回傳 (period_days, custom_date_str)"""
    options = ["1天", "5天", "10天", "20天", "自訂日期"]
    choice = st.radio("比較基準區間", options, horizontal=True, key=f"{key_prefix}_period_radio")
    period_map = {"1天": 1, "5天": 5, "10天": 10, "20天": 20}

    if choice == "自訂日期":
        sorted_dates = sorted(available_date_strs)
        if not sorted_dates:
            st.warning("目前沒有可用的歷史資料日期。")
            return 1, None
        min_d = datetime.datetime.strptime(sorted_dates[0], '%Y%m%d').date()
        max_d = datetime.datetime.strptime(sorted_dates[-1], '%Y%m%d').date()
        picked = st.date_input(
            "選擇比較基準日期",
            value=min_d,
            min_value=min_d,
            max_value=max_d,
            key=f"{key_prefix}_date_input"
        )
        return None, picked.strftime('%Y%m%d')
    else:
        return period_map[choice], None


# 持股資料的「最新資料日期」(用於成分股/持股增減/共同調倉等 CSV-based 區塊顯示)
m_time_global = get_date_from_filename(files[0]) if files else "未知日期"
# 即時股價資料一律顯示「系統當下日期」(用於行情大盤/單檔K線/績效分析等 yfinance-based 區塊)
today_str = datetime.datetime.now().strftime('%Y-%m-%d')

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
# 模組化功能 1: 原始 Yahoo Finance 歷史行情加載 (含 .TWO fallback 與防呆)
# ==========================================
@st.cache_data(ttl=60)
def load_price_data(etf_code, period="2d"):
    """
    嘗試抓取 ETF 歷史股價。
    1. 若要求 period 為 1d/2d，改用 5d 抓取避免假日/休市造成資料不足，再裁切回最後 2 筆。
    2. 先嘗試 .TW (上市)，若抓不到或筆數不足，再嘗試 .TWO (上櫃) 作為 fallback。
    """
    def _try_fetch(suffix, fetch_period):
        try:
            ticker = yf.Ticker(f"{etf_code}{suffix}")
            hist = ticker.history(period=fetch_period)
            if hist is not None and not hist.empty and 'Close' in hist.columns:
                return hist.dropna(subset=['Close'])
            return pd.DataFrame()
        except Exception:
            return pd.DataFrame()

    fetch_period = "5d" if period in ("1d", "2d") else period

    hist = _try_fetch(".TW", fetch_period)
    if len(hist) < 2:
        hist_two = _try_fetch(".TWO", fetch_period)
        if len(hist_two) > len(hist):
            hist = hist_two

    if hist.empty:
        return hist

    if period in ("1d", "2d") and len(hist) > 2:
        hist = hist.tail(2)

    return hist


# ==========================================
# 模組化功能 2: 行情基本資料集建構
# ==========================================
def build_overview_data(etf_codes):
    overview_data = []
    failed_etfs = []
    for etf in etf_codes:
        hist = load_price_data(etf, period="2d")
        etf_display_name = etf_names.get(etf, etf)
        row = {"代碼": etf, "ETF名稱": etf_display_name, "最新價": 0.0, "漲跌價": 0.0, "漲跌幅": 0.0, "成交量": 0}

        if len(hist) >= 2:
            last = hist.iloc[-1]
            prev = hist.iloc[-2]
            prev_close = prev['Close']
            change = last['Close'] - prev_close
            pct = (change / prev_close) * 100 if prev_close not in (0, None) else 0.0
            row["最新價"] = round(float(last['Close']), 2)
            row["漲跌價"] = round(float(change), 2)
            row["漲跌幅"] = round(float(pct), 2)
            row["成交量"] = int(last['Volume']) if 'Volume' in last and pd.notna(last['Volume']) else 0
        elif len(hist) == 1:
            last = hist.iloc[-1]
            row["最新價"] = round(float(last['Close']), 2)
            failed_etfs.append(etf)
        else:
            failed_etfs.append(etf)

        overview_data.append(row)

    st.session_state['_failed_etfs'] = failed_etfs
    return overview_data


# ==========================================
# 主頁面 1: 行情大盤看板
# ==========================================
def render_home_page(overview_list):
    st.title("🏆 台灣主動式 ETF 即時行情大盤")
    st.write(f"資料更新時間：{today_str}")

    st.markdown("""
        <div class="custom-notice-box">
            💡 <strong>使用提示：</strong>點選下方表格清單中的 <strong>ETF名稱</strong> 藍色連結，即可自由進入切換查看該檔 ETF 的「完整成分股明細」與「持股增減異動」。
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.get('_failed_etfs'):
        st.caption(f"⚠️ 以下代碼目前無法從 yfinance 取得足夠的近2日股價資料（可能尚未開盤或資料延遲）：{', '.join(st.session_state['_failed_etfs'])}")

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
                last = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[-1]
                change = last['Close'] - prev['Close']
                pct = (change / prev['Close']) * 100 if prev['Close'] not in (0, None) else 0.0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("目前股價", f"{last['Close']:.2f}")
                c2.metric("漲跌價", f"{change:.2f}", delta=f"{change:.2f}", delta_color="normal" if change >= 0 else "inverse")
                c3.metric("漲跌幅", f"{pct:.2f}%", delta=f"{pct:.2f}%", delta_color="normal" if pct >= 0 else "inverse")
                c4.metric("成交量(股)", f"{int(last['Volume']) if 'Volume' in last and pd.notna(last['Volume']) else 0:,}")

                fig_k = go.Figure(data=[go.Candlestick(
                    x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'],
                    increasing_line_color='#ef4444', decreasing_line_color='#22c55e'
                )])
                fig_k.update_layout(title=f'近 {selected_period} 技術 K 線圖走勢', template='plotly_dark', xaxis_rangeslider_visible=False)
                st.plotly_chart(fig_k, use_container_width=True)
            else:
                st.warning("⚠️ 目前無法取得此 ETF 的歷史股價資料，請稍後再試。")

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
                all_date_strs = [get_file_date_str(f) for f in etf_files]
                period_days, custom_date_str = render_period_selector(f"holding_{selected_etf}", all_date_strs)
                baseline_file = pick_baseline_file(etf_files, period_days, custom_date_str)

                if baseline_file is None:
                    st.warning("⚠️ 找不到符合條件的比較基準資料，目前歷史資料筆數不足，請改選較近的區間或日期。")
                else:
                    baseline_date_display = get_date_from_filename(baseline_file)
                    baseline_idx = etf_files.index(baseline_file)
                    st.caption(f"📅 本次比較區間：{baseline_date_display} → {m_time}（相隔 {baseline_idx} 個交易日）")

                    df_pre = pd.read_csv(os.path.join(data_dir, baseline_file), encoding='utf-8-sig')

                    df_now_cmp = df_now.copy()
                    df_now_cmp['個股名稱'] = df_now_cmp['個股名稱'].astype(str).str.strip()
                    df_pre['個股名稱'] = df_pre['個股名稱'].astype(str).str.strip()

                    df_now_cmp['持有股數'] = pd.to_numeric(df_now_cmp['持有股數'], errors='coerce').fillna(0.0)
                    df_pre['持有股數'] = pd.to_numeric(df_pre['持有股數'], errors='coerce').fillna(0.0)

                    m = pd.merge(df_now_cmp, df_pre, on='個股名稱', how='outer', suffixes=('_now', '_pre')).fillna(0.0)
                    m['張數變動'] = (m['持有股數_now'] - m['持有股數_pre']) / 1000.0

                    status_map = {
                        "🚀 新增持股": (m['持有股數_pre'] == 0) & (m['持有股數_now'] > 0),
                        "🔥 操盤加碼": (m['持有股數_pre'] > 0) & (m['張數變動'] > 0),
                        "⚡ 機構減碼": (m['持有股數_pre'] > 0) & (m['張數變動'] < 0) & (m['持有股數_now'] > 0),
                        "❌ 全額出清": (m['持有股數_pre'] > 0) & (m['持有股數_now'] == 0)
                    }

                    HOLDING_PANEL_HEIGHT = 380

                    cols = st.columns(4)
                    for i, (status, mask) in enumerate(status_map.items()):
                        with cols[i]:
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
            else:
                st.info("目前僅有一筆歷史資料，尚無法進行增減比較。")


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
                ⚠️ <strong>存活過濾機制：</strong>為確保對比公平性，<strong>若 ETF 上市時間未滿所選區間，將自動隱藏不予評比</strong>，避免剛上市新股造成數據失真。<br>
                📅 <strong>區間說明：</strong>「1週/1個月/3個月/6個月」是以「今天」為終點，往回算日曆天數（例如1週=往回7個日曆天），實際對應的交易日會在下方顯示。
            </div>
        """, unsafe_allow_html=True)

        perf_data = []
        min_days_map = {"1週": 4, "1個月": 15, "3個月": 50, "6個月": 100}
        period_map = {"1週": "7d", "1個月": "1mo", "3個月": "3mo", "6個月": "6mo"}
        chart_period = st.radio("選擇圖表對比區間", list(period_map.keys()), horizontal=True, key="analysis_perf_period")

        df_0050 = load_price_data("0050", period=period_map[chart_period])
        benchmark_perf = 0.0
        range_start_str = "未知"
        range_end_str = "未知"
        if not df_0050.empty and len(df_0050) >= 2:
            first_b = df_0050['Close'].iloc[0]
            last_b = df_0050['Close'].iloc[-1]
            benchmark_perf = round(((last_b - first_b) / first_b) * 100, 2) if first_b != 0 else 0.0
            range_start_str = df_0050.index[0].strftime('%Y-%m-%d')
            range_end_str = df_0050.index[-1].strftime('%Y-%m-%d')

        perf_data.append({'ETF': "📌 0050 元大台灣50 (大盤)", '績效(%)': benchmark_perf, '類型': '大盤基準'})

        required_min_days = min_days_map[chart_period]
        failed_perf_etfs = []

        for etf in etf_list:
            hist = load_price_data(etf, period=period_map[chart_period])

            if hist.empty or len(hist) < required_min_days:
                if not hist.empty:
                    failed_perf_etfs.append(etf)
                continue

            etf_display_name = etf_names.get(etf, etf)
            row = {'ETF': etf_display_name, '績效(%)': 0.0, '類型': '主動式 ETF'}

            first_p = hist['Close'].iloc[0]
            last_p = hist['Close'].iloc[-1]
            row['績效(%)'] = round(((last_p - first_p) / first_p) * 100, 2) if first_p != 0 else 0.0
            perf_data.append(row)

        df_perf = pd.DataFrame(perf_data)

        if len(df_perf) <= 1:
            st.warning(f"目前沒有任何主動式 ETF 的上市時間滿足「{chart_period}」的要求。")
        else:
            st.caption(f"📅 本次「{chart_period}」實際比較區間：{range_start_str} → {range_end_str}（共 {len(df_0050)} 個交易日）")

            df_plot = df_perf.sort_values('績效(%)', ascending=False)

            fig_perf = px.bar(
                df_plot,
                x='ETF',
                y='績效(%)',
                text='績效(%)',
                color='類型',
                color_discrete_map={"大盤基準": "#f59e0b", "主動式 ETF": "#38bdf8"},
                title=f"近 {chart_period} 累積績效 vs 0050 大盤對比 (已過濾剛上市不符資格者)"
            )

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

            df_table = df_plot.copy()
            df_table['領先大盤(%)'] = df_table['績效(%)'] - benchmark_perf
            df_table['領先大盤(%)'] = df_table['領先大盤(%)'].apply(lambda x: f"{x:+.2f}%" if x != 0 else "-")
            df_table['績效(%)'] = df_table['績效(%)'].apply(lambda x: f"{x:+.2f}%")

            st.dataframe(df_table.set_index('ETF')[['類型', '績效(%)', '領先大盤(%)']], use_container_width=True)

        if failed_perf_etfs:
            st.caption(f"⚠️ 以下代碼資料筆數不足以計算「{chart_period}」績效（可能剛上市或資料延遲），已自動排除：{', '.join(failed_perf_etfs)}")

    with sub2:
        st.write(f"資料更新時間：{m_time_global}")

        all_dates_global = sorted(set(get_file_date_str(f) for f in files))
        period_days, custom_date_str = render_period_selector("sync_rebalance", all_dates_global)

        all_changes = []
        for etf in etf_list:
            f_list = sorted([f for f in files if f.startswith(etf)], reverse=True)
            baseline_file = pick_baseline_file(f_list, period_days, custom_date_str)

            if baseline_file is not None and len(f_list) >= 1 and baseline_file != f_list[0]:
                d_n = pd.read_csv(os.path.join(data_dir, f_list[0]), encoding='utf-8-sig')
                d_p = pd.read_csv(os.path.join(data_dir, baseline_file), encoding='utf-8-sig')
                d_n['個股名稱'] = d_n['個股名稱'].astype(str).str.strip()
                d_p['個股名稱'] = d_p['個股名稱'].astype(str).str.strip()
                d_n['持有股數'] = pd.to_numeric(d_n['持有股數'], errors='coerce').fillna(0.0)
                d_p['持有股數'] = pd.to_numeric(d_p['持有股數'], errors='coerce').fillna(0.0)
                m = pd.merge(d_n, d_p, on='個股名稱', suffixes=('_n', '_p'))
                m['變動'] = (m['持有股數_n'] - m['持有股數_p']) / 1000
                m['ETF'] = etf
                all_changes.append(m[['個股名稱', '變動', 'ETF']])

        if all_changes:
            if custom_date_str:
                baseline_label = f"{custom_date_str[:4]}-{custom_date_str[4:6]}-{custom_date_str[6:8]}"
            else:
                baseline_label = f"{period_days} 個交易日前"
            st.caption(f"📅 本次比較區間：{baseline_label} → {m_time_global}（僅納入有足夠歷史資料的 ETF）")

            df_all = pd.concat(all_changes)
            c1, c2 = st.columns(2)
            buy_raw = df_all[df_all['變動'] > 0]
            sell_raw = df_all[df_all['變動'] < 0]

            SYNC_PANEL_HEIGHT = 480

            with c1:
                st.markdown('<div class="alignment-title-large">📈 同步加碼/買進凝聚榜 (至少2家以上)</div>', unsafe_allow_html=True)
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
                st.markdown('<div class="alignment-title-large">📉 同步減碼/出清撤退榜 (至少2家以上)</div>', unsafe_allow_html=True)
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
        else:
            st.warning("⚠️ 目前沒有任何 ETF 的歷史資料滿足所選區間，請改選較近的天數或日期。")

    with sub3:
        st.write(f"資料更新時間：{m_time_global}")

        dfs = []
        for etf in etf_list:
            matching_files = [f for f in files if f.startswith(etf)]
            if not matching_files:
                continue
            f_latest = matching_files[0]
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
