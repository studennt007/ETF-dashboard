import streamlit as st
import pandas as pd
import os
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from functools import reduce
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime

# --- 頁面初始配置 ---
st.set_page_config(page_title="Active ETF 監控系統", layout="wide", page_icon="📊")

# --- CSS 注入（優化版：卡片化 / 間距 / hover / 陰影） ---
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

    /* --- 通知卡片 --- */
    .custom-notice-box {
        border: 1px solid #334155 !important;
        padding: 14px 18px !important;
        border-radius: 10px !important;
        margin-bottom: 16px !important;
        background: linear-gradient(135deg, #1e293b 0%, #1a2333 100%) !important;
        font-size: 14px !important;
        color: #cbd5e1 !important;
        line-height: 1.6 !important;
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

    /* --- Metric 卡片化 --- */
    div[data-testid="stMetric"] {
        background-color: #1e293b !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
        padding: 14px 16px !important;
        transition: all 0.15s ease-in-out;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #38bdf8 !important;
        transform: translateY(-2px);
    }
    div[data-testid="stMetricLabel"] { color: #94a3b8 !important; font-size: 13px !important; }
    div[data-testid="stMetricValue"] { font-size: 22px !important; }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #1e293b !important;
        border-color: #334155 !important;
        border-radius: 10px !important;
    }

    /* --- 表格列 hover --- */
    .table-row-hover:hover {
        background-color: #1e293b !important;
        border-radius: 8px;
    }

    div.stButton > button {
        background: transparent !important;
        border: none !important;
        color: #38bdf8 !important;
        text-align: left !important;
        padding: 4px 0 !important;
        margin: 0 !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        transition: color 0.12s ease-in-out;
    }
    div.stButton > button:hover { color: #7dd3fc !important; text-decoration: underline !important; }

    /* --- 主按鈕（返回等）--- */
    div.stButton > button[kind="primary"] {
        background-color: #0284c7 !important;
        color: #ffffff !important;
        padding: 8px 18px !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #0369a1 !important;
        text-decoration: none !important;
    }

    .text-up { color: #ef4444 !important; font-weight: bold; font-size: 15px; }
    .text-down { color: #22c55e !important; font-weight: bold; font-size: 15px; }
    .text-stable { color: #94a3b8 !important; font-size: 15px; }
    .text-normal { color: #f8fafc !important; font-size: 15px; font-weight: 500; }

    /* --- 側邊欄美化 --- */
    section[data-testid="stSidebar"] {
        background-color: #0b1220 !important;
        border-right: 1px solid #1e293b !important;
    }

    /* --- Badge --- */
    .badge {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
        margin-left: 8px;
    }
    .badge-live { background-color: #164e63; color: #67e8f9; }
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
    except Exception:
        return "未知日期"


def get_file_date_str(filename):
    """回傳檔名中的原始日期字串 YYYYMMDD，供排序/比較用"""
    try:
        return filename.split('_')[1].replace('.csv', '')
    except Exception:
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


def pill_selector(label, options, key, horizontal=True):
    """
    以按鈕群組（pill/segmented）取代 st.radio 的圓點樣式。
    優先使用 st.segmented_control（新版 Streamlit），若環境不支援則自動退回自訂按鈕列。
    回傳使用者選擇的字串。
    """
    state_key = f"{key}_pill_value"
    if state_key not in st.session_state:
        st.session_state[state_key] = options[0]

    if hasattr(st, "segmented_control"):
        st.caption(label)
        choice = st.segmented_control(
            label, options, default=st.session_state[state_key],
            key=f"{key}_seg", label_visibility="collapsed",
        )
        if choice is not None:
            st.session_state[state_key] = choice
        return st.session_state[state_key]

    # Fallback：自製按鈕列
    st.caption(label)
    cols = st.columns(len(options))
    for i, opt in enumerate(options):
        is_active = st.session_state[state_key] == opt
        with cols[i]:
            btn_type = "primary" if is_active else "secondary"
            if st.button(opt, key=f"{key}_btn_{opt}", use_container_width=True, type=btn_type):
                st.session_state[state_key] = opt
                st.rerun()
    return st.session_state[state_key]


def render_period_selector(key_prefix, available_date_strs):
    """畫出『1天/5天/10天/20天/自訂日期』選擇器，回傳 (period_days, custom_date_str)"""
    options = ["1天", "5天", "10天", "20天", "自訂日期"]
    choice = pill_selector("比較基準區間", options, key_prefix)
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


def render_risk_metrics_explainer():
    """在風險指標下方顯示計算方式說明，供使用者對照數字來源。"""
    with st.expander("📖 風險指標計算方式說明"):
        st.markdown("""
**年化波動率**
以每日收盤價漲跌幅（日報酬率）的標準差，乘上 √252（一年約252個交易日）換算成年化數字。
數字越大代表價格起伏越劇烈、風險越高。

**最大回撤（MDD）**
把每日報酬率轉成一條累積淨值曲線，計算曲線上任一時間點相對「歷史最高點」的最大跌幅。
代表這段期間若不幸買在最高點、賣在最低點，最慘會虧多少，是衡量下檔風險最直觀的指標。

**簡易 Sharpe 比率**
以「日報酬率平均值 ÷ 日報酬率標準差」年化計算，衡量每承擔一單位風險換到多少報酬。
⚠️ 此處簡化假設無風險利率＝0，因此數字**只適合同期間、同資料源下的相對比較**，不宜與外部公開資料的 Sharpe 直接對照。

**上漲交易日比例**
這段期間內，收盤價較前一日上漲的交易日天數 ÷ 總交易日數，單純反映上漲頻率，不代表漲跌幅大小。

---
💡 以上指標的計算期間會跟著所選的觀察區間變動（例如切換 1個月 / 6個月），區間不同數字會有落差；這是歷史資料回顧，不代表未來風險的保證。
        """)


def compute_risk_metrics(hist: pd.DataFrame) -> dict:
    """用既有的 K 線歷史資料計算年化波動率 / 最大回撤 / 簡易 Sharpe，不需額外抓資料。"""
    if hist is None or len(hist) < 3:
        return {"vol": None, "mdd": None, "sharpe": None, "win_rate": None}

    close = hist['Close'].dropna()
    returns = close.pct_change().dropna()
    if returns.empty:
        return {"vol": None, "mdd": None, "sharpe": None, "win_rate": None}

    annual_vol = returns.std() * (252 ** 0.5) * 100
    cum = (1 + returns).cumprod()
    running_max = cum.cummax()
    drawdown = (cum - running_max) / running_max
    mdd = drawdown.min() * 100
    mean_daily = returns.mean()
    sharpe = (mean_daily / returns.std()) * (252 ** 0.5) if returns.std() != 0 else 0.0
    win_rate = (returns > 0).sum() / len(returns) * 100

    return {"vol": annual_vol, "mdd": mdd, "sharpe": sharpe, "win_rate": win_rate}


@st.cache_data(ttl=300, show_spinner=False)
def load_latest_holdings_all(etf_codes_tuple, files_tuple, data_dir_str):
    """讀取每檔 ETF 最新一份持股 CSV，回傳 {etf: DataFrame}，供反查/重疊度分析共用。"""
    result = {}
    for etf in etf_codes_tuple:
        matching = [f for f in files_tuple if f.startswith(etf)]
        if not matching:
            continue
        f_latest = sorted(matching, reverse=True)[0]
        df = pd.read_csv(os.path.join(data_dir_str, f_latest), encoding='utf-8-sig')
        df['個股名稱'] = df['個股名稱'].astype(str).str.strip()
        df['投資比例(%)'] = pd.to_numeric(df['投資比例(%)'], errors='coerce').fillna(0)
        result[etf] = df
    return result


@st.cache_data(ttl=300, show_spinner=False)
def build_overlap_matrix(etf_codes_tuple, files_tuple, data_dir_str):
    """
    計算 ETF 兩兩持股重疊度（以權重重疊比例 = sum(min(w_a, w_b)) 為指標，0~100）。
    完全基於既有的最新持股 CSV，不需新資料源。
    """
    holdings = load_latest_holdings_all(etf_codes_tuple, files_tuple, data_dir_str)
    codes = [c for c in etf_codes_tuple if c in holdings]
    n = len(codes)
    matrix = pd.DataFrame(0.0, index=codes, columns=codes)

    weight_maps = {c: dict(zip(holdings[c]['個股名稱'], holdings[c]['投資比例(%)'])) for c in codes}

    for i in range(n):
        for j in range(n):
            if i == j:
                matrix.iloc[i, j] = 100.0
                continue
            if j < i:
                matrix.iloc[i, j] = matrix.iloc[j, i]
                continue
            a, b = weight_maps[codes[i]], weight_maps[codes[j]]
            common_stocks = set(a.keys()) & set(b.keys())
            overlap_weight = sum(min(a[s], b[s]) for s in common_stocks)
            matrix.iloc[i, j] = round(overlap_weight, 1)

    return matrix


@st.cache_data(ttl=300, show_spinner=False)
def build_stock_trend(stock_name, etf_codes_tuple, files_tuple, data_dir_str, max_dates=15):
    """
    針對指定個股，掃描所有 ETF 的歷史持股 CSV，統計「每個資料日期」
    有多少檔主動式 ETF 持有該股、以及平均權重，畫出集體增減碼趨勢。
    僅使用既有歷史 CSV，不需新資料源。
    """
    all_dates = sorted(set(get_file_date_str(f) for f in files_tuple), reverse=True)[:max_dates]
    all_dates = sorted(all_dates)  # 由舊到新

    trend_rows = []
    for date_str in all_dates:
        holder_count = 0
        total_weight = 0.0
        for etf in etf_codes_tuple:
            fname = f"{etf}_{date_str}.csv"
            if fname not in files_tuple:
                continue
            try:
                df = pd.read_csv(os.path.join(data_dir_str, fname), encoding='utf-8-sig')
            except Exception:
                continue
            df['個股名稱'] = df['個股名稱'].astype(str).str.strip()
            match = df[df['個股名稱'] == stock_name]
            if not match.empty:
                holder_count += 1
                total_weight += pd.to_numeric(match['投資比例(%)'], errors='coerce').fillna(0).iloc[0]

        trend_rows.append({
            "日期": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}",
            "持有檔數": holder_count,
            "加總權重(%)": round(total_weight, 2),
        })

    return pd.DataFrame(trend_rows)


# 持股資料的「最新資料日期」(用於成分股/持股增減/共同調倉等 CSV-based 區塊顯示)
m_time_global = get_date_from_filename(files[0]) if files else "未知日期"
# 即時股價資料一律顯示「系統當下日期」(用於行情大盤/單檔K線/績效分析等 yfinance-based 區塊)
today_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

# --- 初始化 Session State 狀態機 ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "📈 主動式 ETF 行情大盤"
if "selected_etf" not in st.session_state:
    st.session_state.selected_etf = etf_list[0] if etf_list else ""
if "sort_col" not in st.session_state:
    st.session_state.sort_col = "漲跌幅"
if "sort_desc" not in st.session_state:
    st.session_state.sort_desc = 1

# 側邊欄導航
st.sidebar.title("📊 ETF 監控中心")
st.sidebar.caption(f"共監控 {len(etf_list)} 檔主動式 ETF")
st.sidebar.markdown("---")

nav_items = [
    ("📈 主動式 ETF 行情大盤", "📈 行情大盤看板"),
    ("🌐 多檔市場綜合分析", "🌐 多檔綜合分析"),
]
for page_key, page_label in nav_items:
    is_active = st.session_state.current_page == page_key or (
        page_key == "🌐 多檔市場綜合分析" and st.session_state.current_page in ("🔬 ETF 詳細比較",)
    )
    if st.sidebar.button(
        f"{'● ' if is_active else ''}{page_label}",
        use_container_width=True,
        type="primary" if is_active else "secondary",
    ):
        st.session_state.current_page = page_key
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown("**🔍 快速跳轉至 ETF**")
display_list_sidebar = [etf_names.get(e, e) for e in etf_list]
quick_pick = st.sidebar.selectbox(
    "選擇 ETF 直接查看詳情", display_list_sidebar, index=None,
    placeholder="輸入代碼或名稱搜尋...", label_visibility="collapsed",
)
if quick_pick:
    quick_code = [k for k, v in etf_names.items() if v == quick_pick][0]
    if quick_code != st.session_state.selected_etf or st.session_state.current_page != "📊 單檔詳細分析":
        st.session_state.selected_etf = quick_code
        st.session_state.current_page = "📊 單檔詳細分析"
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(f"⏱️ 股價資料時間：{today_str}")
st.sidebar.caption(f"📁 持股資料日期：{m_time_global}")


# ==========================================
# 模組化功能 1: 原始 Yahoo Finance 歷史行情加載 (含 .TWO fallback 與防呆)
# ==========================================
@st.cache_data(ttl=300, show_spinner=False)
def load_price_data(etf_code, period="2d"):
    """
    嘗試抓取 ETF 歷史股價。
    1. 若要求 period 為 1d/2d，改用 5d 抓取避免假日/休市造成資料不足，再裁切回最後 2 筆。
    2. 先嘗試 .TW (上市)，若抓不到或筆數不足，再嘗試 .TWO (上櫃) 作為 fallback。
    快取時間拉長至 300 秒，減少重複請求造成的頁面延遲。
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


@st.cache_data(ttl=300, show_spinner=False)
def load_price_data_batch(etf_codes, period="2d"):
    """
    平行抓取多檔 ETF 股價，取代逐一序列呼叫。
    回傳 dict：{etf_code: DataFrame}
    """
    results = {}
    with ThreadPoolExecutor(max_workers=min(10, len(etf_codes) or 1)) as executor:
        future_map = {executor.submit(load_price_data, code, period): code for code in etf_codes}
        for future in as_completed(future_map):
            code = future_map[future]
            try:
                results[code] = future.result()
            except Exception:
                results[code] = pd.DataFrame()
    return results


# ==========================================
# 模組化功能 2: 行情基本資料集建構
# ==========================================
def build_overview_data(etf_codes):
    hist_map = load_price_data_batch(tuple(etf_codes), period="2d")

    overview_data = []
    failed_etfs = []
    for etf in etf_codes:
        hist = hist_map.get(etf, pd.DataFrame())
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
    st.caption(f"⏱️ 資料更新時間：{today_str}　·　共 {len(overview_list)} 檔")

    st.markdown("""
        <div class="custom-notice-box">
            💡 <strong>使用提示：</strong>點下方每一列右側的 <strong>「查看詳情 →」</strong> 按鈕，即可切換查看該檔 ETF 的「完整成分股明細」與「持股增減異動」。
        </div>
    """, unsafe_allow_html=True)

    if st.session_state.get('_failed_etfs'):
        st.caption(f"⚠️ 以下代碼目前無法從 yfinance 取得足夠的近2日股價資料（可能尚未開盤或資料延遲）：{', '.join(st.session_state['_failed_etfs'])}")

    total_etfs = len(overview_list)
    up_count = sum(1 for x in overview_list if x["漲跌價"] > 0)
    down_count = sum(1 for x in overview_list if x["漲跌價"] < 0)
    flat_count = total_etfs - up_count - down_count
    avg_pct = sum(x["漲跌幅"] for x in overview_list) / total_etfs if total_etfs > 0 else 0.0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("ETF 總數", f"{total_etfs} 檔")
    m2.metric("上漲家數", f"▲ {up_count} 家")
    m3.metric("下跌家數", f"▼ {down_count} 家")
    m4.metric("平盤家數", f"{flat_count} 家")
    m5.metric("平均漲跌幅", f"{avg_pct:+.2f}%")

    # --- 今日漲跌 TOP5 排行榜（顏色與正負號依實際數值決定，而非依榜單類型） ---
    st.write("")
    lb_up, lb_down = st.columns(2)
    top_up = sorted(overview_list, key=lambda x: x["漲跌幅"], reverse=True)[:5]
    top_down = sorted(overview_list, key=lambda x: x["漲跌幅"])[:5]

    def _pct_span(pct):
        if pct > 0:
            return f"<span class='text-up'>+{pct:.2f}%</span>"
        elif pct < 0:
            return f"<span class='text-down'>{pct:.2f}%</span>"
        return f"<span class='text-stable'>0.00%</span>"

    with lb_up:
        st.markdown('<div class="alignment-title-large" style="font-size:18px;">🔥 今日漲幅 TOP5</div>', unsafe_allow_html=True)
        for r in top_up:
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;padding:4px 8px;'>"
                f"<span class='text-normal'>{r['ETF名稱']}</span>{_pct_span(r['漲跌幅'])}</div>",
                unsafe_allow_html=True,
            )
    with lb_down:
        st.markdown('<div class="alignment-title-large" style="font-size:18px;">🧊 今日跌幅 TOP5</div>', unsafe_allow_html=True)
        for r in top_down:
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;padding:4px 8px;'>"
                f"<span class='text-normal'>{r['ETF名稱']}</span>{_pct_span(r['漲跌幅'])}</div>",
                unsafe_allow_html=True,
            )

    st.write("")
    search_query = st.text_input("🔍 輸入 ETF 代碼或名稱進行即時篩選：", "").strip().lower()

    filtered_list = overview_list
    if search_query:
        filtered_list = [x for x in overview_list if search_query in x["代碼"].lower() or search_query in x["ETF名稱"].lower()]

    if not filtered_list:
        st.info("查無符合條件的 ETF，請調整搜尋關鍵字。")
        return

    st.markdown("<div style='padding: 0px 20px; margin-bottom: 5px;'>", unsafe_allow_html=True)
    h_c1, h_c2, h_c3, h_c4, h_c5, h_c6, h_c7 = st.columns([1, 3, 1.2, 1.2, 1.2, 1.2, 1.3])

    header_mapping = {"代碼": h_c1, "ETF名稱": h_c2, "最新價": h_c3, "漲跌價": h_c4, "漲跌幅": h_c5, "成交量": h_c6}
    for label, col_obj in header_mapping.items():
        with col_obj:
            sort_suffix = " ⇅"
            if st.session_state.sort_col == label:
                if st.session_state.sort_desc == 1:
                    sort_suffix = " ⬇"
                elif st.session_state.sort_desc == 2:
                    sort_suffix = " ⬆"

            if st.button(f"{label}{sort_suffix}", key=f"btn_sort_{label}"):
                if st.session_state.sort_col == label:
                    st.session_state.sort_desc = (st.session_state.sort_desc + 1) % 3
                else:
                    st.session_state.sort_col = label
                    st.session_state.sort_desc = 1
                st.rerun()
    h_c7.markdown("<span class='text-normal'></span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.sort_desc == 1:
        filtered_list = sorted(filtered_list, key=lambda x: x[st.session_state.sort_col], reverse=True)
    elif st.session_state.sort_desc == 2:
        filtered_list = sorted(filtered_list, key=lambda x: x[st.session_state.sort_col], reverse=False)

    for row in filtered_list:
        st.markdown("<div class='table-row-hover'>", unsafe_allow_html=True)
        c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 3, 1.2, 1.2, 1.2, 1.2, 1.3])
        with c1:
            st.markdown(f"<span class='text-normal'>{row['代碼']}</span>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<span class='text-normal'>{row['ETF名稱']}</span>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<span class='text-normal'>{row['最新價']:.2f}</span>", unsafe_allow_html=True)

        if row["漲跌價"] > 0:
            c4.markdown(f"<span class='text-up'>▲ +{row['漲跌價']:.2f}</span>", unsafe_allow_html=True)
            c5.markdown(f"<span class='text-up'>+{row['漲跌幅']:.2f}%</span>", unsafe_allow_html=True)
        elif row["漲跌價"] < 0:
            c4.markdown(f"<span class='text-down'>▼ {row['漲跌價']:.2f}</span>", unsafe_allow_html=True)
            c5.markdown(f"<span class='text-down'>{row['漲跌幅']:.2f}%</span>", unsafe_allow_html=True)
        else:
            c4.markdown("<span class='text-stable'>─ 0.00</span>", unsafe_allow_html=True)
            c5.markdown("<span class='text-stable'>0.00%</span>", unsafe_allow_html=True)

        with c6:
            st.markdown(f"<span class='text-normal'>{row['成交量']:,}</span>", unsafe_allow_html=True)
        with c7:
            if st.button("查看詳情 →", key=f"click_{row['代碼']}", use_container_width=True, type="primary"):
                st.session_state.selected_etf = row["代碼"]
                st.session_state.current_page = "📊 單檔詳細分析"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


# ==========================================
# 主頁面 2: 單檔詳細分析頁面
# ==========================================
def render_single_etf():
    selected_etf = st.session_state.selected_etf
    if selected_etf not in etf_list:
        selected_etf = etf_list[0]
        st.session_state.selected_etf = selected_etf
    selected_display = etf_names.get(selected_etf, selected_etf)

    etf_files = sorted([f for f in files if f.startswith(selected_etf)], reverse=True)
    if etf_files:
        m_time = get_date_from_filename(etf_files[0])
        df_now = pd.read_csv(os.path.join(data_dir, etf_files[0]), encoding='utf-8-sig')

        title_col, back_col = st.columns([5, 1])
        with title_col:
            st.title(f"📊 {selected_display} 分析儀表板")
        with back_col:
            st.write("")
            if st.button("← 返回大盤", type="primary", use_container_width=True):
                st.session_state.current_page = "📈 主動式 ETF 行情大盤"
                st.rerun()

        tab1, tab2, tab3 = st.tabs(["📈 ETF 行情分析", "📋 成分股分析", "🔄 持股增減分析"])

        with tab1:
            st.caption(f"⏱️ 資料更新時間：{today_str}")
            period_map = {"1個月": "1mo", "3個月": "3mo", "6個月": "6mo", "1年": "1y"}
            selected_period = pill_selector("選擇觀察區間", list(period_map.keys()), f"kline_{selected_etf}")

            with st.spinner("正在讀取股價資料..."):
                hist = load_price_data(selected_etf, period=period_map[selected_period])

            if not hist.empty:
                last = hist.iloc[-1]
                prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[-1]
                change = last['Close'] - prev['Close']
                pct = (change / prev['Close']) * 100 if prev['Close'] not in (0, None) else 0.0

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("目前股價", f"{last['Close']:.2f}")
                c2.metric("漲跌價", f"{'+' if change > 0 else ''}{change:.2f}")
                c3.metric("漲跌幅", f"{'+' if pct > 0 else ''}{pct:.2f}%")
                c4.metric("成交量(股)", f"{int(last['Volume']) if 'Volume' in last and pd.notna(last['Volume']) else 0:,}")

                from plotly.subplots import make_subplots

                fig_k = make_subplots(
                    rows=2, cols=1, shared_xaxes=True,
                    row_heights=[0.75, 0.25], vertical_spacing=0.04,
                )
                fig_k.add_trace(go.Candlestick(
                    x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'],
                    increasing_line_color='#ef4444', increasing_fillcolor='#ef4444',
                    decreasing_line_color='#22c55e', decreasing_fillcolor='#22c55e',
                    name='股價', showlegend=False,
                ), row=1, col=1)

                if 'Volume' in hist.columns:
                    vol_colors = ['#ef4444' if c >= o else '#22c55e' for o, c in zip(hist['Open'], hist['Close'])]
                    fig_k.add_trace(go.Bar(
                        x=hist.index, y=hist['Volume'], marker_color=vol_colors,
                        name='成交量', showlegend=False, opacity=0.7,
                    ), row=2, col=1)

                fig_k.update_layout(
                    title=f'近 {selected_period} 技術 K 線走勢',
                    template='plotly_dark',
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis_rangeslider_visible=False,
                    margin=dict(t=50, b=20, l=10, r=10),
                    height=520,
                    hovermode='x unified',
                )
                fig_k.update_xaxes(showgrid=False, rangebreaks=[dict(bounds=["sat", "mon"])], row=1, col=1)
                fig_k.update_xaxes(showgrid=False, rangebreaks=[dict(bounds=["sat", "mon"])], row=2, col=1)
                fig_k.update_yaxes(showgrid=True, gridcolor='#1e293b', row=1, col=1)
                fig_k.update_yaxes(showgrid=True, gridcolor='#1e293b', row=2, col=1, title_text="成交量")
                st.plotly_chart(fig_k, use_container_width=True)

                st.markdown("##### 📐 風險指標（依所選區間計算）")
                risk = compute_risk_metrics(hist)
                r1, r2, r3, r4 = st.columns(4)
                r1.metric("年化波動率", f"{risk['vol']:.2f}%" if risk['vol'] is not None else "—")
                r2.metric("最大回撤", f"{risk['mdd']:.2f}%" if risk['mdd'] is not None else "—")
                r3.metric("簡易 Sharpe", f"{risk['sharpe']:.2f}" if risk['sharpe'] is not None else "—")
                r4.metric("上漲交易日比例", f"{risk['win_rate']:.1f}%" if risk['win_rate'] is not None else "—")
                render_risk_metrics_explainer()
            else:
                st.warning("⚠️ 目前無法取得此 ETF 的歷史股價資料，請稍後再試。")

        with tab2:
            st.caption(f"📁 資料更新時間：{m_time}")
            top_holdings = df_now.nlargest(10, '投資比例(%)')
            fig = px.bar(
                top_holdings, x='投資比例(%)', y='個股名稱', orientation='h',
                title="成分股權重前 10 大分佈", color='投資比例(%)', color_continuous_scale='Blues'
            )
            fig.update_layout(yaxis={'categoryorder': 'total ascending'}, template='plotly_dark', margin=dict(t=50, b=20))
            st.plotly_chart(fig, use_container_width=True)

            target_cols = ['個股名稱', '持有股數', '投資比例(%)']
            display_cols = [c for c in target_cols if c in df_now.columns]

            st.dataframe(df_now[display_cols].copy(), use_container_width=True, hide_index=True)

        with tab3:
            st.caption(f"📁 資料更新時間：{m_time}")
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

                    has_weight_col = '投資比例(%)' in df_now_cmp.columns and '投資比例(%)' in df_pre.columns
                    if has_weight_col:
                        df_now_cmp['投資比例(%)'] = pd.to_numeric(df_now_cmp['投資比例(%)'], errors='coerce').fillna(0.0)
                        df_pre['投資比例(%)'] = pd.to_numeric(df_pre['投資比例(%)'], errors='coerce').fillna(0.0)

                    m = pd.merge(df_now_cmp, df_pre, on='個股名稱', how='outer', suffixes=('_now', '_pre')).fillna(0.0)
                    m['張數變動'] = (m['持有股數_now'] - m['持有股數_pre']) / 1000.0
                    if has_weight_col:
                        m['權重變動'] = m['投資比例(%)_now'] - m['投資比例(%)_pre']
                    else:
                        m['權重變動'] = 0.0

                    status_map = {
                        "🚀 新增持股": (m['持有股數_pre'] == 0) & (m['持有股數_now'] > 0),
                        "🔥 操盤加碼": (m['持有股數_pre'] > 0) & (m['張數變動'] > 0),
                        "⚡ 機構減碼": (m['持有股數_pre'] > 0) & (m['張數變動'] < 0) & (m['持有股數_now'] > 0),
                        "❌ 全額出清": (m['持有股數_pre'] > 0) & (m['持有股數_now'] == 0)
                    }

                    new_count = int(status_map["🚀 新增持股"].sum())
                    add_count = int(status_map["🔥 操盤加碼"].sum())
                    reduce_count = int(status_map["⚡ 機構減碼"].sum())
                    clear_count = int(status_map["❌ 全額出清"].sum())

                    s1, s2, s3, s4 = st.columns(4)
                    s1.metric("新增持股", f"{new_count} 檔")
                    s2.metric("加碼", f"{add_count} 檔")
                    s3.metric("減碼", f"{reduce_count} 檔")
                    s4.metric("出清", f"{clear_count} 檔")

                    st.write("")

                    HOLDING_PANEL_HEIGHT = 380

                    cols = st.columns(4)
                    for i, (status, mask) in enumerate(status_map.items()):
                        with cols[i]:
                            st.markdown(f'<div class="alignment-title-large">{status}</div>', unsafe_allow_html=True)
                            sub_df = m[mask][['個股名稱', '張數變動', '權重變動']].copy()
                            sub_df = sub_df.sort_values('張數變動', ascending=(i == 2 or i == 3))
                            sub_df['張數變動'] = sub_df.apply(
                                lambda r: f"{r['張數變動']:+,.2f} 張 ({r['權重變動']:+.2f}%)", axis=1
                            )
                            sub_df = sub_df[['個股名稱', '張數變動']]
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
    sub1, sub2, sub3, sub4, sub5 = st.tabs([
        "📈 跨週期績效分析", "🔄 共同調倉", "🤝 投信共同持股",
        "🔎 個股反查", "🧬 ETF 重疊度分析",
    ])

    with sub1:
        st.caption(f"⏱️ 資料更新時間：{today_str}")
        st.markdown("""
            <div class="custom-notice-box">
                💡 <strong>嚴格區間對比提示：</strong> 系統已自動加入 <strong>0050 元大台灣50</strong> 作為市場基準線（Benchmark）。<br>
                ⚠️ <strong>存活過濾機制：</strong>為確保對比公平性，<strong>若 ETF 上市時間未滿所選區間，將自動隱藏不予評比</strong>，避免剛上市新股造成數據失真。<br>
                📅 <strong>區間說明：</strong>「1週/1個月/3個月/6個月」是以「今天」為終點，往回算日曆天數（例如1週=往回7個日曆天），實際對應的交易日會在下方顯示。
            </div>
        """, unsafe_allow_html=True)

        min_days_map = {"1週": 4, "1個月": 15, "3個月": 50, "6個月": 100}
        period_map = {"1週": "7d", "1個月": "1mo", "3個月": "3mo", "6個月": "6mo"}
        chart_period = pill_selector("選擇圖表對比區間", list(period_map.keys()), "analysis_perf_period")

        with st.spinner("正在平行抓取各檔 ETF 歷史股價..."):
            df_0050 = load_price_data("0050", period=period_map[chart_period])
            hist_map = load_price_data_batch(tuple(etf_list), period=period_map[chart_period])

        perf_data = []
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
            hist = hist_map.get(etf, pd.DataFrame())

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
            fig_perf.update_layout(xaxis_tickangle=-45, yaxis=dict(ticksuffix="%"), height=550, template='plotly_dark', margin=dict(t=60))
            st.plotly_chart(fig_perf, use_container_width=True)

            df_table = df_plot.copy()
            df_table['領先大盤(%)'] = df_table['績效(%)'] - benchmark_perf
            df_table['領先大盤(%)'] = df_table['領先大盤(%)'].apply(lambda x: f"{x:+.2f}%" if x != 0 else "-")
            df_table['績效(%)'] = df_table['績效(%)'].apply(lambda x: f"{x:+.2f}%")

            st.dataframe(df_table.set_index('ETF')[['類型', '績效(%)', '領先大盤(%)']], use_container_width=True)

        if failed_perf_etfs:
            st.caption(f"⚠️ 以下代碼資料筆數不足以計算「{chart_period}」績效（可能剛上市或資料延遲），已自動排除：{', '.join(failed_perf_etfs)}")

    with sub2:
        st.caption(f"📁 資料更新時間：{m_time_global}")

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
                st.markdown('<div class="alignment-title-large">📈 同步加碼 (至少2家以上)</div>', unsafe_allow_html=True)
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
                st.markdown('<div class="alignment-title-large">📉 同步減碼(至少2家以上)</div>', unsafe_allow_html=True)
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
        st.caption(f"📁 資料更新時間：{m_time_global}")

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

            st.subheader("📋 主動式投信機構共同持股總表")

            st.markdown("""
                <div class="custom-notice-box">
                    📝 <strong>【標記說明】</strong> ★ 核心標記：代表該股票在所有買進它的主動式 ETF 中持股皆大於 1.00% ｜ 持有投信數：代表該股票被多少家主動式 ETF 納入成分股
                </div>
            """, unsafe_allow_html=True)

            st.dataframe(df_disp, use_container_width=True, hide_index=True)

    with sub4:
        st.caption(f"📁 資料更新時間：{m_time_global}")
        st.markdown("""
            <div class="custom-notice-box">
                🔎 <strong>個股反查：</strong>輸入或選擇一檔股票，查看目前有哪些主動式 ETF 持有它、各自權重多少，
                並回顧近期各 ETF「集體」加碼或減碼這檔股票的趨勢（完全基於既有的歷史持股 CSV）。
            </div>
        """, unsafe_allow_html=True)

        holdings_latest = load_latest_holdings_all(tuple(etf_list), tuple(files), data_dir)
        all_stock_names = sorted(set(
            name for df in holdings_latest.values() for name in df['個股名稱'].tolist()
        ))

        picked_stock = st.selectbox("選擇要反查的股票", options=all_stock_names, index=None, placeholder="輸入關鍵字搜尋股票名稱...")

        if picked_stock:
            rows = []
            for etf, df in holdings_latest.items():
                match = df[df['個股名稱'] == picked_stock]
                if not match.empty:
                    rows.append({
                        "ETF代碼": etf,
                        "ETF名稱": etf_names.get(etf, etf),
                        "投資比例(%)": round(float(match['投資比例(%)'].iloc[0]), 2),
                    })

            if rows:
                df_stock = pd.DataFrame(rows).sort_values("投資比例(%)", ascending=False)

                sc1, sc2 = st.columns(2)
                sc1.metric("持有此股的 ETF 家數", f"{len(df_stock)} 家")
                sc2.metric("加總投資比例", f"{df_stock['投資比例(%)'].sum():.2f}%")

                fig_stock = px.bar(
                    df_stock, x="投資比例(%)", y="ETF名稱", orientation="h",
                    title=f"「{picked_stock}」在各 ETF 中的權重分佈",
                    color="投資比例(%)", color_continuous_scale="Blues",
                )
                fig_stock.update_layout(yaxis={'categoryorder': 'total ascending'}, template='plotly_dark', margin=dict(t=50))
                st.plotly_chart(fig_stock, use_container_width=True)
                st.dataframe(df_stock, use_container_width=True, hide_index=True)

                st.markdown("##### 📈 集體增減碼趨勢（近期歷史資料日期）")
                with st.spinner("正在讀取歷史持股快照..."):
                    df_trend = build_stock_trend(picked_stock, tuple(etf_list), tuple(files), data_dir)

                if len(df_trend) >= 2:
                    fig_trend = go.Figure()
                    fig_trend.add_trace(go.Scatter(
                        x=df_trend["日期"], y=df_trend["持有檔數"], name="持有檔數",
                        mode="lines+markers", line=dict(color="#38bdf8"),
                    ))
                    fig_trend.update_layout(
                        title=f"「{picked_stock}」被多少檔主動式 ETF 持有 — 歷史趨勢",
                        template="plotly_dark", margin=dict(t=50), yaxis_title="持有檔數",
                    )
                    st.plotly_chart(fig_trend, use_container_width=True)
                else:
                    st.info("歷史資料筆數不足，暫無法繪製趨勢圖。")
            else:
                st.info("目前沒有任何主動式 ETF 持有這檔股票。")

    with sub5:
        st.caption(f"📁 資料更新時間：{m_time_global}")
        st.markdown("""
            <div class="custom-notice-box">
                🧬 <strong>重疊度分析：</strong>以「兩檔 ETF 共同持有股票的最小權重加總」衡量選股邏輯的相似程度
                （0 = 完全不重疊，100 = 選股與權重幾乎一致），幫助你判斷手上多檔 ETF 是否過度重複配置。
            </div>
        """, unsafe_allow_html=True)

        with st.spinner("正在計算 ETF 兩兩持股重疊度..."):
            overlap_matrix = build_overlap_matrix(tuple(etf_list), tuple(files), data_dir)

        display_labels = [etf_names.get(c, c).split(" ", 1)[-1] for c in overlap_matrix.columns]

        fig_heat = px.imshow(
            overlap_matrix.values,
            x=display_labels, y=display_labels,
            color_continuous_scale="Blues",
            aspect="auto",
            labels=dict(color="重疊度(%)"),
        )
        fig_heat.update_layout(
            title="ETF 兩兩持股重疊度熱力圖",
            template="plotly_dark",
            height=650,
            margin=dict(t=50),
        )
        st.plotly_chart(fig_heat, use_container_width=True)

        st.markdown("##### 🏆 最相似 ETF 配對 TOP10")
        pairs = []
        codes = list(overlap_matrix.columns)
        for i in range(len(codes)):
            for j in range(i + 1, len(codes)):
                pairs.append({
                    "code_a": codes[i], "code_b": codes[j],
                    "ETF A": etf_names.get(codes[i], codes[i]),
                    "ETF B": etf_names.get(codes[j], codes[j]),
                    "重疊度(%)": overlap_matrix.iloc[i, j],
                })
        df_pairs = pd.DataFrame(pairs).sort_values("重疊度(%)", ascending=False).head(10).reset_index(drop=True)

        h1, h2, h3, h4 = st.columns([3, 3, 1.2, 1.3])
        h1.markdown("<span class='text-normal'>ETF A</span>", unsafe_allow_html=True)
        h2.markdown("<span class='text-normal'>ETF B</span>", unsafe_allow_html=True)
        h3.markdown("<span class='text-normal'>重疊度</span>", unsafe_allow_html=True)

        for idx, prow in df_pairs.iterrows():
            c1, c2, c3, c4 = st.columns([3, 3, 1.2, 1.3])
            c1.markdown(f"<span class='text-normal'>{prow['ETF A']}</span>", unsafe_allow_html=True)
            c2.markdown(f"<span class='text-normal'>{prow['ETF B']}</span>", unsafe_allow_html=True)
            c3.markdown(f"<span class='text-normal'>{prow['重疊度(%)']:.1f}%</span>", unsafe_allow_html=True)
            with c4:
                if st.button("🔍 比較", key=f"cmp_pair_{idx}", use_container_width=True, type="primary"):
                    st.session_state['compare_pair'] = (prow['code_a'], prow['code_b'])
                    st.session_state.current_page = "🔬 ETF 詳細比較"
                    st.rerun()


# ==========================================
# 主頁面 4: ETF 詳細比較（獨立頁面）
# ==========================================
def render_etf_compare():
    if not st.session_state.get('compare_pair'):
        st.info("請先從「多檔市場綜合分析 → ETF 重疊度分析」選擇要比較的兩檔 ETF。")
        if st.button("← 返回多檔綜合分析"):
            st.session_state.current_page = "🌐 多檔市場綜合分析"
            st.rerun()
        return

    code_a, code_b = st.session_state['compare_pair']
    name_a, name_b = etf_names.get(code_a, code_a), etf_names.get(code_b, code_b)

    head_col, back_col = st.columns([5, 1])
    with head_col:
        st.title(f"🔬 ETF 詳細比較")
        st.caption(f"{name_a}　vs　{name_b}")
    with back_col:
        st.write("")
        if st.button("← 返回比較列表", type="primary", use_container_width=True):
            st.session_state.current_page = "🌐 多檔市場綜合分析"
            st.rerun()

    holdings_all = load_latest_holdings_all(tuple(etf_list), tuple(files), data_dir)

    # 1) 成分股前10大比較
    st.markdown("#### 📋 成分股權重前 10 大比較")
    hc1, hc2 = st.columns(2)
    for col_obj, code, name in [(hc1, code_a, name_a), (hc2, code_b, name_b)]:
        with col_obj:
            df_h = holdings_all.get(code, pd.DataFrame())
            if not df_h.empty:
                top10 = df_h.nlargest(10, '投資比例(%)')
                fig_h = px.bar(
                    top10, x='投資比例(%)', y='個股名稱', orientation='h',
                    title=name, color_discrete_sequence=['#38bdf8'],
                )
                fig_h.update_layout(
                    yaxis={'categoryorder': 'total ascending'}, template='plotly_dark',
                    margin=dict(t=40), height=380, showlegend=False,
                )
                st.plotly_chart(fig_h, use_container_width=True)
            else:
                st.info("無成分股資料")

    # 2) 績效比較（累積報酬曲線，沿用既有 yfinance 資料）
    st.markdown("#### 📈 近 6 個月累積報酬比較")
    with st.spinner("正在讀取股價資料..."):
        hist_a = load_price_data(code_a, period="6mo")
        hist_b = load_price_data(code_b, period="6mo")

    fig_cmp = go.Figure()
    for hist, name, color in [(hist_a, name_a, '#38bdf8'), (hist_b, name_b, '#f59e0b')]:
        if not hist.empty:
            cum_ret = (hist['Close'] / hist['Close'].iloc[0] - 1) * 100
            fig_cmp.add_trace(go.Scatter(x=hist.index, y=cum_ret, mode='lines', name=name, line=dict(color=color)))
    fig_cmp.update_layout(
        template='plotly_dark', margin=dict(t=20), height=380,
        yaxis_title="累積報酬(%)",
    )
    fig_cmp.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    st.plotly_chart(fig_cmp, use_container_width=True)

    risk_a = compute_risk_metrics(hist_a)
    risk_b = compute_risk_metrics(hist_b)

    # 3) 風險指標比較表
    st.markdown("#### 📐 風險指標比較")
    df_risk_cmp = pd.DataFrame({
        "指標": ["年化波動率(%)", "最大回撤(%)", "簡易Sharpe", "上漲交易日比例(%)"],
        name_a: [
            f"{risk_a['vol']:.2f}" if risk_a['vol'] is not None else "—",
            f"{risk_a['mdd']:.2f}" if risk_a['mdd'] is not None else "—",
            f"{risk_a['sharpe']:.2f}" if risk_a['sharpe'] is not None else "—",
            f"{risk_a['win_rate']:.1f}" if risk_a['win_rate'] is not None else "—",
        ],
        name_b: [
            f"{risk_b['vol']:.2f}" if risk_b['vol'] is not None else "—",
            f"{risk_b['mdd']:.2f}" if risk_b['mdd'] is not None else "—",
            f"{risk_b['sharpe']:.2f}" if risk_b['sharpe'] is not None else "—",
            f"{risk_b['win_rate']:.1f}" if risk_b['win_rate'] is not None else "—",
        ],
    })
    st.dataframe(df_risk_cmp, use_container_width=True, hide_index=True)
    st.caption("⚠️ Sharpe 以無風險利率=0 簡化計算，僅供參考。")
    render_risk_metrics_explainer()


# ==========================================
# 終端路由主渲染控制器
# ==========================================
if st.session_state.current_page == "📈 主動式 ETF 行情大盤":
    with st.spinner("正在平行抓取全部 ETF 即時報價..."):
        raw_market_list = build_overview_data(etf_list)
    render_home_page(raw_market_list)
elif st.session_state.current_page == "📊 單檔詳細分析":
    render_single_etf()
elif st.session_state.current_page == "🔬 ETF 詳細比較":
    render_etf_compare()
else:
    render_market_analysis()
