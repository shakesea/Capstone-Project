import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

# ── Groq AI Analyst ────────────────────────────────────────────────────────
from Groq_analyst import GroqAnalyst, build_context

# ── Currency Configuration ──────────────────────────────────────────────────
IDR_RATE = 3500  # 1 RM = Rp 3,500 (historical conversion rate)

def _c(val):
    """Convert RM to IDR if IDR mode is selected in session state."""
    if st.session_state.get('currency', 'RM') == 'IDR':
        return val * IDR_RATE
    return val

def _fmt_idr(n, fmt=",.0f"):
    """Format number in Indonesian style: . = thousand sep, , = decimal sep."""
    s = format(n, fmt)          # e.g. "1,234,567.89"
    s = s.replace(",", "X")     # "1X234X567.89"
    s = s.replace(".", ",")     # "1X234X567,89"
    s = s.replace("X", ".")     # "1.234.567,89"
    return s

def currency(val, fmt=",.0f"):
    """Format a monetary value: converts RM→IDR if toggle is on, adds correct prefix."""
    prefix = "Rp" if st.session_state.get('currency', 'RM') == 'IDR' else "RM"
    return f"{prefix} {_fmt_idr(_c(val), fmt)}"

def cur_sym():
    """Return currency symbol ('Rp' or 'RM') based on current toggle."""
    return "Rp" if st.session_state.get('currency', 'RM') == 'IDR' else "RM"
# ══════════════════════════════════════════════════════════════════════════════
#  PAGE CONFIG — High-end dark mode
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title='G Coffee Shop — Strategic Intelligence Dashboard',
    page_icon='☕',
    layout='wide',
    initial_sidebar_state='expanded',
)

    # ── Custom dark-theme CSS ────────────────────────────────────────────────────

# ── Helper: hex to rgba for plotly ────────────────────────────────────────────
def hex_to_rgba(hex_color, alpha=0.15):
    """Convert hex color to rgba string for plotly."""
    hex_color = hex_color.lstrip('#')
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f'rgba({r},{g},{b},{alpha})'

# ══════════════════════════════════════════════════════════════════════════════
#  DYNAMIC CSS TOKEN SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

# ── Determine effective theme (instant — no one-run delay) ────────────────
_toggle_val = st.session_state.get('theme_toggle')
if _toggle_val is not None:
    _effective_theme = 'dark' if 'Dark' in _toggle_val else 'light'
else:
    _effective_theme = st.session_state.get('theme', 'dark')

# ── Token values per theme ─────────────────────────────────────────────────
_DARK_TOKENS = {
    # Backgrounds
    'bg-app': '#0E1117',          'bg-card': '#1A1D27',
    'bg-sidebar': '#12141E',      'bg-radio': '#1A1D27',
    'bg-radio-sel': '#2D3142',    'bg-button': '#2D3142',
    'bg-button-hv': '#3D4157',    'bg-alert': '#1A1D27',
    'bg-table': '#1A1D27',        'bg-badge': 'linear-gradient(135deg, #1a1d27, #2a2d3e)',
    # Text
    'txt-primary': '#F0F0F0',     'txt-secondary': '#B0B0C0',
    'txt-muted': '#888',          'txt-inverse': '#FFFFFF',
    'txt-value': '#FFFFFF',       'txt-metric': '#FFFFFF',
    'txt-metric-lbl': '#B0B0C0',  'txt-badge': '#B0B0C0',
    'txt-sb-heading': '#F0F0F0',  'txt-sb-sub': '#888',
    'txt-sb-footer': '#666',      'txt-table': '#E0E0E0',
    'txt-table-hdr': '#B0B0C0',   'txt-btn': '#FFFFFF',
    'bg-chart': '#0E1117',        # chart pie-line border
    # Borders & misc
    'border': '#2D3142',          'border-badge': '#3d4157',
    'shadow-card': 'none',
}

_LIGHT_TOKENS = {
    # Backgrounds — Nordic Warm Light (krem-slate lembut, premium, ergonomis)
    'bg-app': '#FDFBF7',          'bg-card': '#FFFFFF',
    'bg-sidebar': '#F4F1EA',      'bg-radio': '#FFFFFF',
    'bg-radio-sel': '#EAE4D9',    'bg-button': '#FFFFFF',
    'bg-button-hv': '#F0ECE3',    'bg-alert': '#FFFFFF',
    'bg-table': '#FFFFFF',        'bg-badge': '#F0ECE3',
    # Text — slate arang pekat, kontras tinggi, mudah dibaca
    'txt-primary': '#252F3F',     'txt-secondary': '#4A5568',
    'txt-muted': '#718096',       'txt-inverse': '#252F3F',
    'txt-value': '#252F3F',       'txt-metric': '#252F3F',
    'txt-metric-lbl': '#718096',  'txt-badge': '#4A5568',
    # Sidebar text — slate arang pekat, paksa teks menu keluar dari efek nyaru
    'txt-sb-heading': '#252F3F',  'txt-sb-sub': '#4A5568',
    'txt-sb-footer': '#94A3B8',   'txt-table': '#252F3F',
    'txt-table-hdr': '#4A5568',   'txt-btn': '#252F3F',
    'bg-chart': '#E2E8F0',        # chart pie-line border
    # Borders & misc — senada dengan bg-sidebar
    'border': '#E8E2D6',          'border-badge': '#E8E2D6',
    'shadow-card': '0 1px 3px rgba(0,0,0,0.05)',
}

# ── Build CSS variable block ───────────────────────────────────────────────
def _build_tokens(theme):
    """Return CSS :root block for the given theme."""
    src = _DARK_TOKENS if theme == 'dark' else _LIGHT_TOKENS
    lines = [':root {']
    for k, v in src.items():
        lines.append(f'  --{k}: {v};')
    lines.append('}')
    return '\n'.join(lines)

_theme_tokens = _build_tokens(_effective_theme)

# ── Base CSS (all rules use var() tokens) ──────────────────────────────────
_BASE_CSS = """
/* ── Misc helpers ── */
.stApp { background-color: var(--bg-app); }

/* ── Main content headings & text ── */
section[data-testid="stMain"] h1,
section[data-testid="stMain"] h2,
section[data-testid="stMain"] h3,
section[data-testid="stMain"] h4,
section[data-testid="stMain"] p,
section[data-testid="stMain"] .stMarkdown p,
section[data-testid="stMain"] .stMarkdown span,
section[data-testid="stMain"] .stMarkdown div:not([class*="insight"]):not([class*="badge"]) {
    color: var(--txt-primary) !important;
}

hr { border-color: var(--border); }

/* ── Analytical Lens Switcher (segmented control style) ── */
div[data-testid="stHorizontalBlock"]:has(> div > label[for="lens_radio"]) {
    background: var(--bg-radio) !important;
    border-radius: 8px !important;
    padding: 2px !important;
    display: inline-flex !important;
    width: auto !important;
    gap: 0 !important;
}
div[data-testid="stHorizontalBlock"]:has(> div > label[for="lens_radio"]) > div {
    flex: 0 0 auto !important;
    padding: 0 2px !important;
}
div[data-testid="stHorizontalBlock"]:has(> div > label[for="lens_radio"]) .stRadio label {
    color: var(--txt-secondary) !important;
    padding: 6px 16px !important;
    border-radius: 6px !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
}
div[data-testid="stHorizontalBlock"]:has(> div > label[for="lens_radio"]) .stRadio label:has(input:checked) {
    background: var(--bg-card) !important;
    color: var(--txt-primary) !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1) !important;
}

/* ── Insight cards ── */
.insight-card {
    background-color: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 20px;
    margin: 8px 0;
    box-shadow: var(--shadow-card);
}
.insight-card h4 {
    color: var(--txt-secondary); font-size: 0.85rem;
    text-transform: uppercase; letter-spacing: 0.5px; margin: 0 0 8px 0;
}
.insight-card .value { color: var(--txt-value); font-size: 2rem; font-weight: 700; }
.insight-card .sub  { color: var(--txt-muted); font-size: 0.8rem; }

/* ── Business badge ── */
.business-badge {
    background: var(--bg-badge);
    border: 1px solid var(--border-badge); border-radius: 8px;
    padding: 6px 14px; display: inline-block;
    color: var(--txt-badge); font-size: 0.8rem; margin: 2px;
}

/* ── Sidebar ── */
/* Streamlit renders sidebar as <section> — NOT <div> */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div:first-child {
    background-color: var(--bg-sidebar) !important;
    border-right: 1px solid var(--border);
}
/* Sidebar: ALL markdown text, headings, labels — forced dark-teduh */
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown div,
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] h4,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stSelectbox label {
    color: var(--txt-sb-heading) !important;
}
/* Sidebar radio — clean text list (no circles, theme-aware highlight) */
/* opacity:1 + txt-primary paksa teks menu keluar dari efek nyaru */
section[data-testid="stSidebar"] .stRadio [role="radio"] {
    color: var(--txt-primary) !important;
    opacity: 1 !important;
    border-radius: 6px !important;
    padding: 4px 10px !important;
    margin: 1px 0 !important;
    transition: all 0.15s ease !important;
    cursor: pointer !important;
}
/* Hide the radio circle / bullet entirely */
section[data-testid="stSidebar"] .stRadio [role="radio"] > span:first-child {
    display: none !important;
}
/* Active item — teks tetap gelap pekat, highlight via bg-radio-sel */
section[data-testid="stSidebar"] .stRadio [role="radio"][aria-checked="true"] {
    background-color: var(--bg-radio-sel) !important;
    color: var(--txt-primary) !important;
    opacity: 1 !important;
    font-weight: 500 !important;
}
/* Hover state */
section[data-testid="stSidebar"] .stRadio [role="radio"]:hover {
    background-color: var(--bg-radio-sel) !important;
}
/* Sidebar: universal force — semua anak elemen teks jadi gelap pekat */
section[data-testid="stSidebar"] *,
section[data-testid="stSidebar"] .stRadio [role="radio"] *,
section[data-testid="stSidebar"] .stRadio label span {
    color: var(--txt-primary) !important;
    opacity: 1 !important;
}
/* Sidebar active item — semua anak elemen tetap gelap */
section[data-testid="stSidebar"] [aria-checked="true"] *,
section[data-testid="stSidebar"] [aria-checked="true"] span {
    color: var(--txt-primary) !important;
}

/* ── Metric cards ── */
.stMetric {
    background-color: var(--bg-card); border-radius: 12px;
    padding: 16px; border: 1px solid var(--border);
}
.stMetric label { color: var(--txt-metric-lbl); font-size: 0.85rem; }
.stMetric [data-testid="stMetricValue"] {
    color: var(--txt-metric); font-size: 1.8rem; font-weight: 700;
}

/* ── DataFrames ── */
/* HANYA target kontainer utama — tanpa wildcard, tanpa role="grid" */
.stDataFrame,
div[data-testid="stDataFrame"] {
    background-color: var(--bg-table) !important;
}
/* Teks di dalam data grid — tanpa merusak posisi canvas Glide */
div[data-testid="stDataFrame"] [data-testid="styled-data-grid"] {
    color: var(--txt-table) !important;
}
/* Header row — kontras gelap */
.stDataFrame div[role="columnheader"],
div[data-testid="stDataFrame"] div[role="columnheader"] {
    font-weight: 600 !important;
    color: var(--txt-table-hdr) !important;
    background-color: var(--bg-table) !important;
}
/* HTML table fallback untuk custom markdown tables */
table td, table th,
.stTable td, .stTable th {
    color: var(--txt-primary) !important;
    background-color: var(--bg-table) !important;
    border-color: var(--border) !important;
}

/* ── Radio groups ── */
.stRadio [data-testid="stRadioLabel"] { color: var(--txt-secondary) !important; }
.stRadio [role="radiogroup"] { background-color: var(--bg-radio); border: 1px solid var(--border); border-radius: 8px; padding: 4px; }
/* Sidebar: radiogroup becomes a clean list (no border/bg) */
section[data-testid="stSidebar"] .stRadio [role="radiogroup"] {
    background: none !important;
    border: none !important;
    padding: 0 !important;
}
.stRadio [role="radio"] { color: var(--txt-secondary) !important; }
.stRadio [role="radio"][aria-checked="true"] { background-color: var(--bg-radio-sel); color: var(--txt-inverse) !important; }
section[data-testid="stSidebar"] .stRadio [data-testid="stRadioLabel"] { color: var(--txt-secondary) !important; }

/* ── Selectbox & Slider labels ── */
.stSelectbox label, .stSlider label { color: var(--txt-muted); }

/* ── Alerts ── */
.stAlert { background-color: var(--bg-alert); border: 1px solid var(--border); color: var(--txt-table); }

/* ── Buttons (general) ── */
.stButton button {
    background-color: var(--bg-button); color: var(--txt-btn);
    border: 1px solid var(--border); border-radius: 8px; padding: 8px 20px; font-weight: 500;
}
.stButton button:hover { background-color: var(--bg-button-hv); }

/* ── Theme toggle icon button (top-right) ── */
div[data-testid="stButton-testid-theme_btn"] {
    position: absolute !important;
    top: 12px !important;
    right: 35px !important;
    z-index: 9999 !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: visible !important;
}
div[data-testid="stButton-testid-theme_btn"] button {
    position: absolute !important;
    top: 0 !important;
    right: 0 !important;
    background: none !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    padding: 0 8px !important;
    font-size: 1.15rem !important;
    min-width: auto !important;
    min-height: auto !important;
    line-height: 1.6 !important;
    height: auto !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stButton-testid-theme_btn"] button:hover {
    background-color: var(--bg-button-hv) !important;
}

/* ── Dropdown / Selectbox (bajak widget hitam) ── */
div[data-testid="stSelectbox"] div[data-baseweb="select"],
div[data-testid="stSelectbox"] ul[role="listbox"],
div[data-testid="stSelectbox"] li {
    background-color: var(--bg-card) !important;
    color: var(--txt-primary) !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
div[data-testid="stSelectbox"] div[data-baseweb="select"] input {
    color: var(--txt-primary) !important;
}

/* ── Widget text (slider, multi-select) ── */
.stMultiSelect div[data-baseweb="select"] *,
.stSlider div[data-baseweb="slider"] [role="slider"] + div,
.stSlider [data-testid="stThumbValue"],
.stSlider [data-testid="stTickBar"] * {
    color: var(--txt-primary) !important;
}

/* ── Inline style overrides (controlled by token vars) ── */
[style*="color:#888"],   [style*="color: #888"]   { color: var(--txt-muted) !important; }
[style*="color:#B0B0C0"],[style*="color: #B0B0C0"]{ color: var(--txt-secondary) !important; }
[style*="color:#E0E0E0"],[style*="color: #E0E0E0"]{ color: var(--txt-table) !important; }
[style*="color:#F0F0F0"],[style*="color: #F0F0F0"]{ color: var(--txt-primary) !important; }
[style*="color:#666"],  [style*="color: #666"]   { color: var(--txt-sb-footer) !important; }
[style*="color:#555"],  [style*="color: #555"]   { color: var(--txt-muted) !important; }
[style*="border-color:#2D3142"],[style*="border-color: #2D3142"]{ border-color: var(--border) !important; }
"""

# ── Inject theme tokens + base CSS ─────────────────────────────────────────
st.markdown(f'<style>\n{_theme_tokens}\n\n{_BASE_CSS}\n</style>', unsafe_allow_html=True)

# ── Sync session state ─────────────────────────────────────────────────────
st.session_state.theme = _effective_theme

# ── Chart color theme helper ───────────────────────────────────────────────
def chart_theme():
    """Plotly theme dictionary sourced from the same CSS tokens."""
    tokens = _DARK_TOKENS if _effective_theme == 'dark' else _LIGHT_TOKENS
    return {
        'font': tokens['txt-table'],
        'grid': tokens['border'],
        'axis': tokens['txt-muted'],
        'legend': tokens['txt-table'],
        'pie_line': tokens['bg-chart'],
    }

CT = chart_theme()

# ══════════════════════════════════════════════════════════════════════════════
#  DATA PATHS
# ══════════════════════════════════════════════════════════════════════════════
BASE = Path(__file__).parent.resolve()

MEMBER_META   = BASE / 'member_cluster_metadata.json'
GUEST_META    = BASE / 'guest_cluster_metadata.json'
MEMBER_RULES  = BASE / 'df_rules_member.parquet'
GUEST_RULES   = BASE / 'df_rules_guest.parquet'
MEMBER_SEG    = BASE / 'df_member_with_segments.parquet'
GUEST_SEG     = BASE / 'df_guest_with_segments.parquet'
MENU_DATA     = BASE / 'menu_cleaned.parquet'
FC_HWR        = BASE / 'df_forecast_90days_HWR-XGB.parquet'
FC_PROPHET    = BASE / 'df_forecast_90days_Prophet-XGB.parquet'
FC_SARIMA     = BASE / 'df_forecast_90days_SARIMA-XGB.parquet'
TRANS_FEATURES = BASE / 'df_transaction_features.parquet'

# ══════════════════════════════════════════════════════════════════════════════
#  HELPER: LOADERS
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

@st.cache_data
def load_parquet(path):
    """Read parquet, handle categorical type issues."""
    import pyarrow.parquet as pq
    try:
        return pd.read_parquet(path)
    except TypeError:
        # If categorical dtype fails, read with pyarrow directly
        tbl = pq.read_table(str(path))
        return tbl.to_pandas()

@st.cache_data
def load_forecast(path):
    """Load forecast parquet safely."""
    import pyarrow.parquet as pq
    tbl = pq.read_table(str(path))
    return tbl.to_pandas()

@st.cache_data
def load_segment_counts(path, col='segment_name'):
    import pyarrow.parquet as pq
    tbl = pq.read_table(str(path), columns=[col])
    from collections import Counter
    counts = Counter(tbl.column(col).to_pylist())
    return pd.DataFrame([
        {'segment': k, 'count': v, 'pct': round(v / len(tbl) * 100, 1)}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ])

@st.cache_data
def load_menu():
    return pd.read_parquet(MENU_DATA)

@st.cache_data
def load_transaction_sample():
    """Load a sample of transaction features for avg calculations."""
    import pyarrow.parquet as pq
    tbl = pq.read_table(str(TRANS_FEATURES), columns=['final_amount', 'basket_size', 'discount_applied'])
    # Take a representative sample
    sample = tbl.slice(0, 500000)
    return sample.to_pandas()

@st.cache_data
def load_historical_daily():
    """Daily transaction counts + revenue aggregated by city (2023-07 to 2025-06)."""
    import pyarrow.parquet as pq
    tbl = pq.read_table(str(TRANS_FEATURES), columns=['city', 'created_at', 'final_amount'])
    df = tbl.to_pandas()
    df['date'] = pd.to_datetime(df['created_at']).dt.normalize()
    daily = df.groupby(['date', 'city'], as_index=False).agg(
        total_transactions=('final_amount', 'count'),
        total_revenue=('final_amount', 'sum'),
    )
    daily = daily.sort_values(['date', 'city']).reset_index(drop=True)
    return daily


# ══════════════════════════════════════════════════════════════════════════════
#  FINANCIAL ENGINE (Ref: 00-Cogs)
# ══════════════════════════════════════════════════════════════════════════════

class FinancialEngine:
    """
    Calculates key financial metrics per transaction and per bundle.
    Based on menu-level pricing with estimated cost structures.
    """

    # Typical coffee shop cost assumptions (as fraction of retail)
    COGS_RATIO = 0.32        # Cost of Goods Sold (raw materials ~32%)
    OPEX_PER_TRANSACTION = 2.50  # Fixed operating cost per transaction (labour, utilities, rent分摊)

    def __init__(self, menu_df):
        self.menu = menu_df.set_index('item_name')['price'].to_dict()
        self.avg_price = menu_df['price'].mean()

    def get_cogs(self, item_name):
        """Estimate raw material cost for an item."""
        price = self.menu.get(item_name, self.avg_price)
        return price * self.COGS_RATIO

    def get_operating_cost(self):
        """Per-transaction operating cost (labour, rent, utilities)."""
        return self.OPEX_PER_TRANSACTION

    def get_net_margin(self, item_name, discount=0.0):
        """
        Net Profit Margin = Price - COGS - OpCost - Discount
        Returns both absolute margin and margin ratio.
        """
        price = self.menu.get(item_name, self.avg_price)
        cogs = price * self.COGS_RATIO
        op_cost = self.OPEX_PER_TRANSACTION
        discount_abs = price * discount
        net = price - cogs - op_cost - discount_abs
        return {
            'item': item_name,
            'price': price,
            'cogs': cogs,
            'operating_cost': op_cost,
            'discount': discount_abs,
            'net_profit': net,
            'net_margin_pct': (net / price * 100) if price > 0 else 0,
        }

    def get_bundle_margin(self, items, discount=0.0):
        """Calculate combined margin for a bundle of items."""
        total = {'price': 0, 'cogs': 0, 'op_cost': 0, 'discount': 0, 'net': 0}
        for item in items:
            m = self.get_net_margin(item.strip(), discount)
            total['price'] += m['price']
            total['cogs'] += m['cogs']
            total['op_cost'] += m['operating_cost']
            total['discount'] += m['discount']
            total['net'] += m['net_profit']
        total['margin_pct'] = (total['net'] / total['price'] * 100) if total['price'] > 0 else 0
        return total

    def price_sensitivity(self, item_name, pct_change):
        """Return new margin if price changes by pct_change (e.g., 0.10 = +10%)."""
        base = self.get_net_margin(item_name)
        new_price = base['price'] * (1 + pct_change)
        # COGS stays same (raw material cost doesn't change with retail price)
        new_net = new_price - base['cogs'] - base['operating_cost'] - base['discount']
        return {
            'original_price': base['price'],
            'new_price': new_price,
            'original_net': base['net_profit'],
            'new_net': new_net,
            'margin_impact': new_net - base['net_profit'],
        }


# ══════════════════════════════════════════════════════════════════════════════
#  FORECAST ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class ForecastEngine:
    """
    Wraps both forecast models with business-friendly labels.
    HWR-XGB -> 'Conservative Growth' (stable, trend-following)
    Prophet-XGB -> 'Aggressive Growth' (captures more inflection, higher upside)
    """

    LABELS = {
        'HWR-XGB': 'Conservative Growth',
        'Prophet-XGB': 'Aggressive Growth',
        'SARIMA-XGB': 'Balanced Growth',
    }

    def __init__(self):
        self.conservative = load_forecast(FC_HWR)
        self.aggressive = load_forecast(FC_PROPHET)
        # Add model label
        self.conservative['scenario'] = self.LABELS.get('HWR-XGB', 'Conservative Growth')
        self.aggressive['scenario'] = self.LABELS.get('Prophet-XGB', 'Aggressive Growth')
        # Combine
        self.full = pd.concat([self.conservative, self.aggressive], ignore_index=True)
        self.full['created_at'] = pd.to_datetime(self.full['created_at'])

        # Derive average transaction value from historical data
        tx_sample = load_transaction_sample()
        self.avg_transaction_value = float(tx_sample['final_amount'].mean())

    def get_profit_forecast(self, margin_pct=0.25):
        """
        Convert transaction forecasts to profit forecasts.
        margin_pct: estimated net profit margin on each transaction.
        Uses FinancialEngine's typical margin per transaction.
        """
        df = self.full.copy()
        # Revenue forecast
        df['projected_revenue'] = df['total_transactions'] * self.avg_transaction_value
        # Profit forecast (net of all costs)
        df['projected_profit'] = df['projected_revenue'] * margin_pct
        return df

    def get_bundle_impact_forecast(self, bundle_name, margin_pct=0.25, boost_factor=0.08):
        """
        Simulate the projected profit increase if a specific bundle is launched.
        boost_factor: estimated % increase in transactions due to bundle promo.
        """
        df = self.get_profit_forecast(margin_pct)
        df['bundle_boost'] = df['total_transactions'] * boost_factor
        df['boosted_transactions'] = df['total_transactions'] + df['bundle_boost']
        df['boosted_profit'] = df['boosted_transactions'] * self.avg_transaction_value * margin_pct
        df['profit_increase'] = df['boosted_profit'] - df['projected_profit']
        df['bundle_name'] = bundle_name
        return df


# ══════════════════════════════════════════════════════════════════════════════
#  BUSINESS LANGUAGE MAP
# ══════════════════════════════════════════════════════════════════════════════

BUSINESS_COLUMNS = {
    'support': 'Popularity Score',
    'confidence': 'Projected Success Rate',
    'lift': 'Cross-Sell Potential',
    'antecedents': 'Product A',
    'consequents': 'Product B',
    'leverage': 'Upsell Opportunity',
    'conviction': 'Dependency Strength',
}

SEGMENT_DESCRIPTIONS = {
    'At Risk Regulars': 'Loyal customers who haven\'t visited recently — reactivation opportunity',
    'New Occasional': 'New customers with low visit frequency — nurture into regulars',
    'Hibernating': 'Long-absent customers — re-engagement campaign target',
    'Champions': 'Best customers — highest frequency & spending — VIP treatment',
    'Big Spender': 'High-value guests with large basket sizes',
    'Weekend Visitor': 'Weekend-only traffic — target with weekday promotions',
    'Deal Hunter': 'Discount-sensitive — coupon & voucher-driven purchases',
    'Quick Buy': 'Single-item, fast transactions — impulse buy opportunities',
}

# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE INIT
# ══════════════════════════════════════════════════════════════════════════════

if 'selected_bundle' not in st.session_state:
    st.session_state.selected_bundle = None
if 'bundle_source' not in st.session_state:
    st.session_state.bundle_source = None
if 'scenario_params' not in st.session_state:
    st.session_state.scenario_params = {'price_adj': 0.0, 'stock_level': 0.0, 'discount_intensity': 0.0}
if 'forecast_fullscreen' not in st.session_state:
    st.session_state.forecast_fullscreen = False
if 'theme' not in st.session_state:
    st.session_state.theme = 'dark'
if 'dashboard_lens' not in st.session_state:
    st.session_state.dashboard_lens = 'Profit'

# ══════════════════════════════════════════════════════════════════════════════
#  LOAD ALL DATA
# ══════════════════════════════════════════════════════════════════════════════

menu_df = load_menu()
fin_engine = FinancialEngine(menu_df)
fc_engine = ForecastEngine()

member_meta = load_json(MEMBER_META)
guest_meta = load_json(GUEST_META)
member_rules = load_parquet(MEMBER_RULES)
guest_rules = load_parquet(GUEST_RULES)
member_seg_counts = load_segment_counts(MEMBER_SEG)
guest_seg_counts = load_segment_counts(GUEST_SEG)

# ── Gemini AI Analyst ─────────────────────────────────────────────────────────
gemini = GroqAnalyst()

# ── Color palette for dark mode ──────────────────────────────────────────────
DARK_COLORS = [
    '#6C5CE7', '#00B894', '#FDAA5E', '#E17055',
    '#0984E3', '#A29BFE', '#55EFC4', '#FAB1A0',
    '#74B9FF', '#81ECEC', '#FDCB6E', '#E17055',
]

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR NAVIGATION
# ══════════════════════════════════════════════════════════════════════════════

st.sidebar.markdown("""
<div style="display:flex;align-items:center;gap:12px;margin-bottom:24px;">
    <span style="font-size:2rem;">☕</span>
    <div>
        <div style="font-weight:700;font-size:1.2rem;color:#F0F0F0;">G Coffee Shop</div>
        <div style="font-size:0.75rem;color:#888;">Strategic Intelligence</div>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown('<hr style="border-color:#2D3142;">', unsafe_allow_html=True)

nav_tabs = [
    '📊  Overview',
    '👥  Customer Segments',
    '🛒  Bundle Intelligence',
    '📈  Forecast & Profit',
    '🔬  Strategic Explorer',
    '🤖  AI Analyst',
]

selected_tab = st.sidebar.radio('Navigation', nav_tabs, index=0, label_visibility='collapsed')

# ── Segment audience filter in sidebar ───────────────────────────────────────
st.sidebar.markdown('<hr style="border-color:#2D3142;">', unsafe_allow_html=True)
audience = st.sidebar.radio(
    'Customer Group',
    ['Members', 'Guests (Non-Members)'],
    help='Toggle between member loyalty segments and guest behavioral clusters',
    key='audience_filter',
)

st.sidebar.markdown('<hr style="border-color:#2D3142;">', unsafe_allow_html=True)

# ── Currency toggle ─────────────────────────────────────────────────────────
currency_choice = st.sidebar.selectbox(
    'Currency',
    ['RM', 'IDR'],
    format_func=lambda x: f'{x} (Rp)' if x == 'IDR' else x,
    help='Display values in Ringgit Malaysia or Indonesian Rupiah (1 RM = Rp 3,500)',
    key='currency',
)

st.sidebar.markdown('<hr style="border-color:#2D3142;">', unsafe_allow_html=True)
st.sidebar.markdown(
    '<div style="color:#666;font-size:0.7rem;text-align:center;padding:8px;">'
    'G Coffee Shop · Prescriptive Analytics v2.0</div>',
    unsafe_allow_html=True
)

# ── Determine which rules / meta to use ──────────────────────────────────────
if audience == 'Members':
    rules_df = member_rules
    meta = member_meta
    seg_counts = member_seg_counts
    is_member = True
    # Override k if it doesn't match actual profiles (member_meta has k=2 but 4 profiles)
    if 'cluster_profiles' in meta:
        meta['k'] = len(meta['cluster_profiles'])
else:
    rules_df = guest_rules
    meta = guest_meta
    seg_counts = guest_seg_counts
    is_member = False
    # Normalize key for guest metadata
    if 'optimal_k' in meta:
        meta['k'] = meta['optimal_k']




# ══════════════════════════════════════════════════════════════════════════════
#  RENDER FUNCTIONS FOR EACH TAB
# ══════════════════════════════════════════════════════════════════════════════

def render_overview():
    """📊 Overview Dashboard — key metrics at a glance."""

    st.markdown('<h2>📊 Business Overview</h2>', unsafe_allow_html=True)

    # ── Lens-aware mode ────────────────────────────────────────────────────
    _rev = st.session_state.get('dashboard_lens', 'Profit') == 'Revenue'

    # ── Key Metrics Row ────────────────────────────────────────────────────
    total_customers = meta.get('total_members', seg_counts['count'].sum())
    n_segments = len(seg_counts)

    # Average profit per transaction from financial engine
    avg_margin = fin_engine.get_net_margin('Latte')
    avg_profit_pct = avg_margin['net_margin_pct']

    # Total projected daily profit/revenue from forecast
    profit_fc = fc_engine.get_profit_forecast(margin_pct=avg_profit_pct / 100)
    avg_daily_profit = profit_fc.groupby('scenario')['projected_profit'].mean().mean()
    avg_daily_revenue = profit_fc.groupby('scenario')['projected_revenue'].mean().mean()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="insight-card">
            <h4>Total Customers</h4>
            <div class="value">{total_customers:,.0f}</div>
            <div class="sub">Across {n_segments} behavioral segments</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if _rev:
            avg_rev_per_tx = fc_engine.avg_transaction_value
            st.markdown(f"""
            <div class="insight-card">
                <h4>Avg Revenue / Transaction</h4>
                <div class="value" style="color:#00B894;">{currency(avg_rev_per_tx, '.2f')}</div>
                <div class="sub">Across all branches & periods</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="insight-card">
                <h4>Avg Net Profit / Transaction</h4>
                <div class="value">{currency(avg_margin['net_profit'], '.2f')}</div>
                <div class="sub">Margin: {avg_profit_pct:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
    with col3:
        if _rev:
            st.markdown(f"""
            <div class="insight-card">
                <h4>Projected Daily Revenue</h4>
                <div class="value" style="color:#00B894;">{currency(avg_daily_revenue, ',.0f')}</div>
                <div class="sub">90-day forward estimate</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="insight-card">
                <h4>Projected Daily Profit</h4>
                <div class="value">{currency(avg_daily_profit, ',.0f')}</div>
                <div class="sub">90-day forward estimate</div>
            </div>
            """, unsafe_allow_html=True)
    with col4:
        n_bundles = len(rules_df) if rules_df is not None else 0
        st.markdown(f"""
        <div class="insight-card">
            <h4>Cross-Sell Opportunities</h4>
            <div class="value">{n_bundles:,}</div>
            <div class="sub">Product pairs with high potential</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Two-column: Segment distribution + Mini profit chart ───────────────
    dist_col, chart_col = st.columns([1, 1.5])

    with dist_col:
        st.markdown('<h4>📋 Customer Segment Mix</h4>', unsafe_allow_html=True)

        fig_pie = px.pie(
            seg_counts,
            values='count',
            names='segment',
            title=None,
            color_discrete_sequence=DARK_COLORS,
            hole=0.45,
        )
        fig_pie.update_traces(
            textposition='outside',
            textinfo='percent+label',
            marker=dict(line=dict(color=CT['pie_line'], width=2)),
            textfont=dict(color=CT['font']),
        )
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color=CT['font'],
            margin=dict(l=20, r=20, t=10, b=20),
            legend=dict(font=dict(color=CT['legend'])),
            height=350,
        )
        st.plotly_chart(fig_pie, width='stretch')

    with chart_col:
        _chart_title = '📈 90-Day Revenue Outlook' if _rev else '📈 90-Day Profit Outlook'
        st.markdown(f'<h4>{_chart_title}</h4>', unsafe_allow_html=True)

        profit_fc = fc_engine.get_profit_forecast(margin_pct=avg_profit_pct / 100)
        # Aggregate across all cities per day per scenario
        _metric_col = 'projected_revenue' if _rev else 'projected_profit'
        _label = f'Revenue ({cur_sym()})' if _rev else f'Profit ({cur_sym()})'
        agg = profit_fc.groupby(['created_at', 'scenario'])[
            _metric_col
        ].sum().reset_index()

        fig_line = px.line(
            agg,
            x='created_at',
            y=_metric_col,
            color='scenario',
            title=None,
            color_discrete_map={
                'Conservative Growth': '#6C5CE7',
                'Aggressive Growth': '#00B894',
            },
            labels={'created_at': '', _metric_col: _label, 'scenario': ''},
        )
        fig_line.update_traces(
            line=dict(width=2.5),
            hovertemplate=f'<b>%{{x|%b %d}}</b><br>{_label.split()[0]}: {cur_sym()} %{{y:,.0f}}',
        )
        fig_line.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color=CT['font'],
            xaxis=dict(showgrid=False, color=CT['axis']),
            yaxis=dict(showgrid=True, gridcolor=CT['grid'], color=CT['axis']),
            legend=dict(font=dict(color=CT['legend']), orientation='h', y=1.08),
            margin=dict(l=40, r=20, t=10, b=40),
            hovermode='x unified',
            height=350,
        )
        st.plotly_chart(fig_line, width='stretch')

    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Bottom row: Menu pricing snapshot ──────────────────────────────────
    st.markdown('<h4>☕ Menu Profitability Snapshot</h4>', unsafe_allow_html=True)

    menu_margins = []
    for _, row in menu_df.iterrows():
        m = fin_engine.get_net_margin(row['item_name'])
        menu_margins.append(m)

    menu_profit_df = pd.DataFrame(menu_margins)

    fig_menu = px.bar(
        menu_profit_df,
        x='item',
        y=['price', 'cogs', 'net_profit'],
        title=None,
        barmode='group',
        color_discrete_map={
            'price': '#6C5CE7',
            'cogs': '#E17055',
            'net_profit': '#00B894',
        },
        labels={'value': f'Amount ({cur_sym()})', 'item': '', 'variable': ''},
    )
    fig_menu.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=CT['font'],
        xaxis=dict(showgrid=False, color=CT['axis']),
        yaxis=dict(showgrid=True, gridcolor=CT['grid'], color=CT['axis']),
        legend=dict(font=dict(color=CT['legend']), orientation='h', y=1.08),
        margin=dict(l=40, r=20, t=10, b=40),
        height=350,
    )
    st.plotly_chart(fig_menu, width='stretch')


def render_segments():
    """👥 Customer Segments — profiles with business-friendly language."""

    if is_member:
        st.markdown('<h2>👥 Member Loyalty Segments</h2>', unsafe_allow_html=True)
        st.markdown(
            '<div style="color:#888;margin-bottom:16px;">'
            'Based on Recency, Frequency & Monetary value — '
            'showing how customers engage with the brand.</div>',
            unsafe_allow_html=True
        )

        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        col1.metric('Total Members', f"{meta['total_members']:,}")
        col2.metric('Segments', meta['k'])

        # Segment distribution
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<h4>📊 Segment Distribution</h4>', unsafe_allow_html=True)

        dist_col1, dist_col2 = st.columns([1, 1.5])

        fig_pie = px.pie(
            seg_counts, values='count', names='segment',
            title=None, color_discrete_sequence=DARK_COLORS, hole=0.4,
        )
        fig_pie.update_traces(
            textposition='outside', textinfo='percent+label',
            marker=dict(line=dict(color=CT['pie_line'], width=2)),
            textfont=dict(color=CT['font']),
        )
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color=CT['font'], margin=dict(l=20, r=20, t=10, b=20),
            legend=dict(font=dict(color=CT['legend'])), height=350,
        )
        dist_col1.plotly_chart(fig_pie, width='stretch')

        dist_col2.dataframe(
            seg_counts.style.format({'pct': '{:.1f}%', 'count': '{:,}'}),
            hide_index=True, width='stretch',
        )

        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<h4>📋 Segment Profiles</h4>', unsafe_allow_html=True)

        profiles = []
        for p in meta['cluster_profiles']:
            seg_name = meta['cluster_labels'][str(p['cluster'])]
            desc = SEGMENT_DESCRIPTIONS.get(seg_name, '')
            profiles.append({
                'Segment': seg_name,
                'Description': desc,
                'Customers': f"{p['count']:,}",
                'Size': f"{p['pct']:.1f}%",
                'Avg Visit Gap': f"{p['R_mean']:.0f} days",
                'Avg Visits': f"{p['F_mean']:.1f}",
                'Avg Spend': currency(p['M_mean'], ',.0f'),
                'Revenue Share': f"{p['revenue_share_pct']:.1f}%",
            })
        st.dataframe(
            pd.DataFrame(profiles),
            hide_index=True,
            width='stretch',
            column_config={
                'Description': st.column_config.TextColumn(width='large'),
            }
        )

        # RFM Radar
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<h4>📈 Loyalty Profile Comparison</h4>', unsafe_allow_html=True)

        max_r = max(p['R_mean'] for p in meta['cluster_profiles'])
        max_f = max(p['F_mean'] for p in meta['cluster_profiles'])
        max_m = max(p['M_mean'] for p in meta['cluster_profiles'])

        fig_radar = go.Figure()
        for i, p in enumerate(meta['cluster_profiles']):
            seg_name = meta['cluster_labels'][str(p['cluster'])]
            fig_radar.add_trace(go.Scatterpolar(
                r=[
                    1 - p['R_mean'] / max_r,
                    p['F_mean'] / max_f,
                    p['M_mean'] / max_m,
                    1 - p['R_mean'] / max_r,
                ],
                theta=['Visit Frequency (higher=better)', 'Visit Count', 'Total Spend', 'Visit Frequency'],
                name=seg_name,
                fill='toself',
                line_color=DARK_COLORS[i % len(DARK_COLORS)],
            ))
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(visible=True, range=[0, 1], color=CT['axis']),
                bgcolor='rgba(0,0,0,0)',
            ),
            showlegend=True,
            paper_bgcolor='rgba(0,0,0,0)',
            font_color=CT['font'],
            legend=dict(font=dict(color=CT['legend'])),
            height=400,
        )
        st.plotly_chart(fig_radar, width='stretch')

    else:
        st.markdown('<h2>👥 Guest Behavioral Segments</h2>', unsafe_allow_html=True)
        st.markdown(
            '<div style="color:#888;margin-bottom:16px;">'
            'Based on transaction behavior — basket size, spending, visit timing, and voucher usage.</div>',
            unsafe_allow_html=True
        )

        col1, col2, col3 = st.columns(3)
        col1.metric('Total Guest Transactions', f"{seg_counts['count'].sum():,}")
        col2.metric('Segments', meta['optimal_k'])

        # Segment distribution
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<h4>📊 Segment Distribution</h4>', unsafe_allow_html=True)

        dist_col1, dist_col2 = st.columns([1, 1.5])

        fig_pie = px.pie(
            seg_counts, values='count', names='segment',
            title=None, color_discrete_sequence=DARK_COLORS, hole=0.4,
        )
        fig_pie.update_traces(
            textposition='outside', textinfo='percent+label',
            marker=dict(line=dict(color=CT['pie_line'], width=2)),
            textfont=dict(color=CT['font']),
        )
        fig_pie.update_layout(
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            font_color=CT['font'], margin=dict(l=20, r=20, t=10, b=20),
            legend=dict(font=dict(color=CT['legend'])), height=350,
        )
        dist_col1.plotly_chart(fig_pie, width='stretch')

        dist_col2.dataframe(
            seg_counts.style.format({'pct': '{:.1f}%', 'count': '{:,}'}),
            hide_index=True, width='stretch',
        )

        # Segment descriptions
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown('<h4>📋 Segment Profiles</h4>', unsafe_allow_html=True)

        seg_info = []
        for cid, cname in meta['cluster_id_to_name'].items():
            desc = SEGMENT_DESCRIPTIONS.get(cname, '')
            seg_info.append({'Segment': cname, 'Description': desc})
        st.dataframe(pd.DataFrame(seg_info), hide_index=True, width='stretch')

    # ── Model info expander (kept but de-emphasized) ──────────────────────
    with st.expander('ℹ️ Additional Information'):
        st.markdown(
            '<div style="color:#888;font-size:0.85rem;">'
            'Segments were identified using behavioral clustering on transaction history. '
            'Each group shares similar purchasing patterns and responds differently to promotions.</div>',
            unsafe_allow_html=True
        )


def render_bundles():
    """🛒 Bundle Intelligence — clickable rules with business terms, updates forecast."""

    st.markdown('<h2>🛒 Bundle Intelligence</h2>', unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#888;margin-bottom:16px;">'
        'Discover product pairs that customers frequently buy together. '
        '<strong>Click any bundle</strong> to see its projected profit impact on the 90-day forecast.</div>',
        unsafe_allow_html=True
    )

    if rules_df is None or len(rules_df) == 0:
        st.warning('No bundle rules available for this customer group.')
        return

    # Sort rules by lift descending (use local copy to avoid shadowing module-level rules_df)
    sorted_rules = rules_df.sort_values('lift', ascending=False).reset_index(drop=True)

    # ── Filters (business terms) — only show slider if metric has variation ─
    conf_min = float(sorted_rules['confidence'].min())
    conf_max = float(sorted_rules['confidence'].max())
    lift_min = float(sorted_rules['lift'].min())
    lift_max = float(sorted_rules['lift'].max())

    _has_conf_var = conf_max > conf_min
    _has_lift_var = lift_max > lift_min

    col_filt1, col_filt2 = st.columns(2)

    if _has_conf_var:
        min_success = col_filt1.slider(
            'Min Projected Success Rate',
            conf_min, conf_max, conf_min,
            step=0.001,
            format='%.3f',
            help='Higher success rate = stronger likelihood that buying Product A leads to buying Product B',
        )
        _conf_cond = sorted_rules['confidence'] >= min_success
    else:
        col_filt1.markdown(
            '<div style="color:#888;font-size:0.85rem;">✅ Success Rate: <strong>varies naturally</strong></div>',
            unsafe_allow_html=True,
        )
        _conf_cond = pd.Series(True, index=sorted_rules.index)

    if _has_lift_var:
        min_potential = col_filt2.slider(
            'Min Cross-Sell Potential',
            lift_min, lift_max, lift_min,
            step=0.001,
            format='%.3f',
            help='Higher cross-sell potential = products that are more often bought together',
        )
        _lift_cond = sorted_rules['lift'] >= min_potential
    else:
        col_filt2.markdown(
            '<div style="color:#888;font-size:0.85rem;">✅ Cross-Sell Potential: <strong>1.0</strong> (all pairings are independent)</div>',
            unsafe_allow_html=True,
        )
        _lift_cond = pd.Series(True, index=sorted_rules.index)

    filtered = sorted_rules[_conf_cond & _lift_cond]

    st.caption(f'Showing {len(filtered)} of {len(sorted_rules)} bundle opportunities')
    # If filter is too restrictive, show a hint
    if len(filtered) == 0:
        st.info('No bundles match these criteria. Try lowering the thresholds.')
        filtered = sorted_rules  # fallback: show all sorted

    # ── Display table with clickable rows ─────────────────────────────────
    display_df = filtered[[
        'antecedents', 'consequents', 'support', 'confidence', 'lift'
    ]].copy()
    display_df.columns = [
        'Product A', 'Product B',
        'Popularity Score', 'Projected Success Rate', 'Cross-Sell Potential',
    ]

    # Format
    styled = display_df.style.format({
        'Popularity Score': '{:.1%}',
        'Projected Success Rate': '{:.1%}',
        'Cross-Sell Potential': '{:.3f}',
    })

    # Make it interactive - each row is a button to select bundle
    st.markdown('<h4>📋 Available Product Bundles</h4>', unsafe_allow_html=True)

    # Create a selection mechanism using a grid of buttons
    # Show top 20 bundles as quick-select chips
    top_bundles = filtered.head(20)

    st.markdown('<div style="color:#B0B0C0;font-size:0.85rem;margin-bottom:8px;">Quick-select a bundle:</div>', unsafe_allow_html=True)

    # Display bundle buttons in rows of 3
    cols_per_row = 3
    for i in range(0, min(len(top_bundles), 15), cols_per_row):
        cols = st.columns(cols_per_row)
        for j in range(cols_per_row):
            idx = i + j
            if idx < len(top_bundles):
                row = top_bundles.iloc[idx]
                bundle_label = f"{row['antecedents']} + {row['consequents']}"
                # Show confidence as "success rate"
                success_pct = f"{row['confidence']*100:.0f}%"
                with cols[j]:
                    if st.button(
                        f"☕ {bundle_label}",
                        key=f"bundle_{idx}",
                        help=f"Projected Success Rate: {success_pct} | Cross-Sell Potential: {row['lift']:.2f}",
                        width='stretch',
                    ):
                        st.session_state.selected_bundle = bundle_label
                        st.session_state.bundle_source = audience
                        st.rerun()

    st.markdown('<br>', unsafe_allow_html=True)

    # ── Show full browseable table ────────────────────────────────────────
    with st.expander('🔍 Browse all bundles', expanded=True):
        st.dataframe(
            styled,
            hide_index=True,
            width='stretch',
            height=400,
        )

    # ── Selected Bundle Impact Preview ────────────────────────────────────
    if st.session_state.selected_bundle:
        st.markdown('<hr>', unsafe_allow_html=True)
        bundle_name = st.session_state.selected_bundle
        source_seg = st.session_state.bundle_source

        st.markdown(f'<h4>📦 Bundle Selected: {bundle_name}</h4>', unsafe_allow_html=True)
        st.markdown(
            f'<div style="color:#888;">For segment: <strong>{source_seg}</strong> — '
            'Showing projected profit uplift if this bundle is launched as a promo.</div>',
            unsafe_allow_html=True
        )

        # Get forecast impact
        avg_margin = fin_engine.get_net_margin('Latte')
        margin_pct = avg_margin['net_margin_pct'] / 100

        # Find the rule to get confidence level as boost factor
        match = filtered[
            (filtered['antecedents'] + ' + ' + filtered['consequents'] == bundle_name)
        ]
        if len(match) == 0:
            # Try reverse order
            match = filtered[
                (filtered['consequents'] + ' + ' + filtered['antecedents'] == bundle_name)
            ]
        if len(match) > 0:
            confidence = float(match.iloc[0]['confidence'])
            lift_val = float(match.iloc[0]['lift'])
        else:
            confidence = 0.20
            lift_val = 0.70

        # Boost factor derived from confidence + lift
        boost_factor = confidence * lift_val * 0.15  # Scale to realistic boost

        impact_df = fc_engine.get_bundle_impact_forecast(
            bundle_name, margin_pct=margin_pct, boost_factor=boost_factor
        )

        # Aggregate across cities
        agg_impact = impact_df.groupby(
            ['created_at', 'scenario']
        )[['projected_profit', 'profit_increase']].sum().reset_index()

        # Total projected increase
        total_increase = agg_impact.groupby('scenario')['profit_increase'].sum()
        total_profit = agg_impact.groupby('scenario')['projected_profit'].sum()

        # Format numbers compactly to avoid overflow in narrow columns
        def _fmt(v):
            pfx = cur_sym()
            cv = _c(v)  # converted value (RM→IDR if applicable)
            if cv >= 1_000_000:
                return f'{pfx} {_fmt_idr(cv/1_000_000, ".1f")} Jt'
            elif cv >= 1_000:
                return f'{pfx} {_fmt_idr(cv/1_000, ".0f")} Rb'
            return f'{pfx} {_fmt_idr(cv, ".0f")}'

        col_imp1, col_imp2 = st.columns(2)
        with col_imp1:
            total_inc = total_increase.sum()
            cons_inc = total_increase.get('Conservative Growth', 0)
            aggr_inc = total_increase.get('Aggressive Growth', 0)
            st.markdown(f"""
            <div class="insight-card" style="word-break:break-word;">
                <div style="color:#B0B0C0;font-size:0.85rem;margin-bottom:8px;">Projected Profit Increase (90 days)</div>
                <div class="value" style="color:#00B894;">{_fmt(total_inc)}</div>
                <div class="sub">
                    Conservative: {_fmt(cons_inc)}<br>
                    Aggressive: {_fmt(aggr_inc)}
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_imp2:
            pct_boost = (total_inc / total_profit.sum() * 100) if total_profit.sum() > 0 else 0
            st.markdown(f"""
            <div class="insight-card" style="word-break:break-word;">
                <div style="color:#B0B0C0;font-size:0.85rem;margin-bottom:8px;">Uplift vs Baseline</div>
                <div class="value" style="color:#6C5CE7;">+{pct_boost:.1f}%</div>
                <div class="sub">Expected profit uplift from this bundle promotion</div>
            </div>
            """, unsafe_allow_html=True)

        # Visualize impact
        fig_impact = go.Figure()

        for scenario in agg_impact['scenario'].unique():
            sdata = agg_impact[agg_impact['scenario'] == scenario]
            fig_impact.add_trace(go.Scatter(
                x=sdata['created_at'],
                y=sdata['projected_profit'],
                mode='lines',
                name=f'{scenario} (Baseline)',
                line=dict(
                    color='#6C5CE7' if 'Conservative' in scenario else '#00B894',
                    width=1.5, dash='dot',
                ),
            ))
            fig_impact.add_trace(go.Scatter(
                x=sdata['created_at'],
                y=sdata['projected_profit'] + sdata['profit_increase'],
                mode='lines',
                name=f'{scenario} (With Bundle)',
                line=dict(
                    color='#6C5CE7' if 'Conservative' in scenario else '#00B894',
                    width=2.5,
                ),
            ))

        fig_impact.update_layout(
            title=f'Profit Forecast: "{bundle_name}" Bundle Impact',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color=CT['font'],
            xaxis=dict(showgrid=False, color=CT['axis']),
            yaxis=dict(showgrid=True, gridcolor=CT['grid'], color=CT['axis'], title=f'Profit ({cur_sym()})'),
            legend=dict(font=dict(color=CT['legend']), orientation='h', y=1.12),
            margin=dict(l=40, r=20, t=50, b=40),
            hovermode='x unified',
            height=450,
        )
        st.plotly_chart(fig_impact, width='stretch')

        # ── Also show the rule details ────────────────────────────────────
        if len(match) > 0:
            st.markdown('<hr>', unsafe_allow_html=True)
            st.markdown('<h4>📋 Bundle Performance Indicators</h4>', unsafe_allow_html=True)

            detail = match.iloc[0]
            det1, det2, det3 = st.columns(3)
            det1.markdown(f"""
            <div class="insight-card">
                <h4>Popularity Score</h4>
                <div class="value">{detail['support']*100:.1f}%</div>
                <div class="sub">How common this combination is</div>
            </div>
            """, unsafe_allow_html=True)
            det2.markdown(f"""
            <div class="insight-card">
                <h4>Projected Success Rate</h4>
                <div class="value">{detail['confidence']*100:.1f}%</div>
                <div class="sub">Likelihood Product A leads to Product B</div>
            </div>
            """, unsafe_allow_html=True)
            det3.markdown(f"""
            <div class="insight-card">
                <h4>Cross-Sell Potential</h4>
                <div class="value">{detail['lift']:.2f}</div>
                <div class="sub">> 1.0 = strong pairing, < 1.0 = frequent solo purchase</div>
            </div>
            """, unsafe_allow_html=True)

    else:
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown(
            '<div style="text-align:center;padding:40px;color:#666;">'
            '👆 Click a bundle above to see its projected profit impact</div>',
            unsafe_allow_html=True
        )


def render_forecast():
    """📈 Forecast & Profit — dual-model side-by-side view + fullscreen historical."""

    fs = st.session_state.forecast_fullscreen
    _rev_ft = st.session_state.get('dashboard_lens', 'Profit') == 'Revenue'
    _ft_label = 'Revenue' if _rev_ft else 'Profit'
    _ft_metric = 'projected_revenue' if _rev_ft else 'projected_profit'

    # ── Header row with fullscreen toggle ─────────────────────────────────
    col_hdr, col_btn = st.columns([4, 1])
    with col_hdr:
        if fs:
            st.markdown(f'<h2>📈 Historical & {_ft_label} Forecast Overview</h2>', unsafe_allow_html=True)
        else:
            st.markdown(f'<h2>📈 {_ft_label} Forecast — Next 90 Days</h2>', unsafe_allow_html=True)
    with col_btn:
        btn_label = '⛶ Exit Fullscreen' if fs else '⛶ Fullscreen'
        if st.button(btn_label, key='fs_toggle_btn', width='stretch'):
            st.session_state.forecast_fullscreen = not fs
            st.rerun()

    # ── Common: compute profit forecast ────────────────────────────────────
    avg_margin = fin_engine.get_net_margin('Latte')
    margin_pct = avg_margin['net_margin_pct'] / 100
    profit_fc = fc_engine.get_profit_forecast(margin_pct=margin_pct)

    # ═══════════════════════════════════════════════════════════════════════
    #  FULLSCREEN MODE — Combined Historical + Forecast
    # ═══════════════════════════════════════════════════════════════════════
    if fs:
        hist = load_historical_daily()
        # Convert historical transactions → profit & revenue using avg transaction value
        hist['projected_revenue'] = hist['total_transactions'] * fc_engine.avg_transaction_value
        hist['projected_profit'] = hist['projected_revenue'] * margin_pct

        # ── Controls row ──
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 2, 1])
        branches = sorted(hist['city'].unique())
        date_min = hist['date'].min().date()
        date_max = max(
            hist['date'].max().date(),
            profit_fc['created_at'].max().date(),
        )

        with col_ctrl1:
            sel_branches = st.multiselect(
                'Select Branch(es)',
                branches,
                default=branches,
                key='fs_branches',
            )
            if not sel_branches:
                sel_branches = branches  # fallback
        with col_ctrl2:
            dr = st.date_input(
                'Time Period',
                value=(date_min, date_max),
                min_value=date_min,
                max_value=date_max,
                key='fs_daterange',
            )
            if isinstance(dr, tuple) and len(dr) == 2:
                dr_start, dr_end = dr
            else:
                dr_start, dr_end = date_min, date_max
        with col_ctrl3:
            st.markdown('<div style="margin-top:24px;"></div>', unsafe_allow_html=True)
            if st.button('🔄 Reset View', key='fs_reset', width='stretch'):
                for k in ['fs_branches', 'fs_daterange']:
                    if k in st.session_state:
                        del st.session_state[k]
                st.rerun()

        # ── Filter data ──
        hist_f = hist[
            (hist['city'].isin(sel_branches))
            & (hist['date'] >= pd.Timestamp(dr_start))
            & (hist['date'] <= pd.Timestamp(dr_end))
        ].copy()

        fc_f = profit_fc[
            (profit_fc['branch'].isin(sel_branches))
            & (profit_fc['created_at'] >= pd.Timestamp(dr_start))
            & (profit_fc['created_at'] <= pd.Timestamp(dr_end))
        ].copy()

        # Aggregate across selected branches (lens-aware: _ft_metric)
        hist_agg = hist_f.groupby('date', as_index=False)[_ft_metric].sum()
        fc_agg = fc_f.groupby(['created_at', 'scenario'], as_index=False)[_ft_metric].sum()

        # ── Build combined chart ──
        fig_fs = go.Figure()

        # Historical trace
        fig_fs.add_trace(go.Scatter(
            x=hist_agg['date'],
            y=hist_agg[_ft_metric],
            mode='lines',
            name='Historical',
            line=dict(color='#888', width=1.5),
            hovertemplate=f'<b>%{{x|%b %Y}}</b><br>{_ft_label}: {cur_sym()} %{{y:,.0f}}<br>',
        ))

        # Forecast traces (with confidence bands)
        for scenario in ['Conservative Growth', 'Aggressive Growth']:
            sdata = fc_agg[fc_agg['scenario'] == scenario]
            color = '#6C5CE7' if scenario == 'Conservative Growth' else '#00B894'
            band_pct = 0.05 if 'Conservative' in scenario else 0.08

            fig_fs.add_trace(go.Scatter(
                x=sdata['created_at'],
                y=sdata[_ft_metric],
                mode='lines',
                name=scenario,
                line=dict(color=color, width=2.5),
                hovertemplate=f'<b>%{{x|%b %d}}</b><br>{_ft_label}: {cur_sym()} %{{y:,.0f}}<br>',
            ))

            # Confidence band
            upper = sdata[_ft_metric] * (1 + band_pct)
            lower = sdata[_ft_metric] * (1 - band_pct)
            fig_fs.add_trace(go.Scatter(
                x=pd.concat([sdata['created_at'], sdata['created_at'][::-1]]),
                y=pd.concat([upper, lower[::-1]]),
                fill='toself',
                fillcolor=hex_to_rgba(color, 0.12),
                line=dict(width=0),
                showlegend=False,
                hoverinfo='skip',
            ))

        # Forecast start marker
        fc_start = profit_fc['created_at'].min()
        fig_fs.add_shape(
            type='line',
            x0=fc_start, x1=fc_start,
            y0=0, y1=1, yref='paper',
            line=dict(dash='dash', color='#E17055', width=1.5),
        )
        fig_fs.add_annotation(
            x=fc_start, y=1, yref='paper',
            text='Forecast Start',
            showarrow=False,
            font=dict(color='#E17055', size=12),
            yshift=10,
        )

        fig_fs.update_layout(
            title=f'{_ft_label} Overview — {", ".join(sel_branches[:3])}{" +" if len(sel_branches) > 3 else ""}',
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color=CT['font'],
            xaxis=dict(showgrid=False, color=CT['axis'], title=''),
            yaxis=dict(showgrid=True, gridcolor=CT['grid'], color=CT['axis'], title=f'Daily {_ft_label} ({cur_sym()})'),
            legend=dict(font=dict(color=CT['legend']), orientation='h', y=1.08),
            margin=dict(l=40, r=20, t=50, b=40),
            hovermode='x unified',
            height=600,
        )
        st.plotly_chart(fig_fs, width='stretch')

        # ── Summary metrics below chart ──
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            total_hist = hist_agg[_ft_metric].sum()
            st.markdown(f"""
            <div class="insight-card">
                <h4>Historical {_ft_label}</h4>
                <div class="value" style="color:#888;">{currency(total_hist, ',.0f')}</div>
                <div class="sub">{hist_f['date'].nunique():,} days · {len(sel_branches)} branch(es)</div>
            </div>
            """, unsafe_allow_html=True)
        with col_s2:
            cons_fs = fc_agg[fc_agg['scenario'] == 'Conservative Growth'][_ft_metric].sum()
            st.markdown(f"""
            <div class="insight-card">
                <h4>Conservative Growth</h4>
                <div class="value" style="color:#6C5CE7;">{currency(cons_fs, ',.0f')}</div>
                <div class="sub">Stable 90-day projection</div>
            </div>
            """, unsafe_allow_html=True)
        with col_s3:
            aggr_fs = fc_agg[fc_agg['scenario'] == 'Aggressive Growth'][_ft_metric].sum()
            st.markdown(f"""
            <div class="insight-card">
                <h4>Aggressive Growth</h4>
                <div class="value" style="color:#00B894;">{currency(aggr_fs, ',.0f')}</div>
                <div class="sub">Higher upside 90-day projection</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown(
            '<div style="text-align:center;color:#555;margin-top:12px;">'
            f'Showing <strong>{hist_f["city"].nunique()}</strong> branch(es) — '
            f'{dr_start} to {dr_end} · '
            'Use filters above to narrow scope'
            '</div>',
            unsafe_allow_html=True,
        )
        return  # ── end fullscreen mode ──

    # ═══════════════════════════════════════════════════════════════════════
    #  NORMAL VIEW (existing code preserved)
    # ═══════════════════════════════════════════════════════════════════════

    st.markdown(
        '<div style="color:#888;margin-bottom:16px;">'
        'Two forecast scenarios based on your transaction history. '
        'Use these to plan inventory, staffing, and promotions.</div>',
        unsafe_allow_html=True
    )

    # ── Key numbers ───────────────────────────────────────────────────────
    agg_fc = profit_fc.groupby('scenario')[_ft_metric].sum().reset_index()

    col_fc1, col_fc2, col_fc3 = st.columns(3)

    cons_val = agg_fc[agg_fc['scenario'] == 'Conservative Growth'][_ft_metric].values
    aggr_val = agg_fc[agg_fc['scenario'] == 'Aggressive Growth'][_ft_metric].values

    cons_val = cons_val[0] if len(cons_val) > 0 else 0
    aggr_val = aggr_val[0] if len(aggr_val) > 0 else 0

    _color_cons = '#6C5CE7'
    with col_fc1:
        st.markdown(f"""
        <div class="insight-card">
            <h4>Conservative Growth (90d)</h4>
            <div class="value" style="color:{_color_cons};">{currency(cons_val, ',.0f')}</div>
            <div class="sub">Stable trend projection</div>
        </div>
        """, unsafe_allow_html=True)
    with col_fc2:
        st.markdown(f"""
        <div class="insight-card">
            <h4>Aggressive Growth (90d)</h4>
            <div class="value" style="color:#00B894;">{currency(aggr_val, ',.0f')}</div>
            <div class="sub">Higher upside potential</div>
        </div>
        """, unsafe_allow_html=True)
    with col_fc3:
        diff = aggr_val - cons_val
        diff_pct = (diff / cons_val * 100) if cons_val > 0 else 0
        st.markdown(f"""
        <div class="insight-card">
            <h4>Growth Gap</h4>
            <div class="value" style="color:#FDAA5E;">+{diff_pct:.1f}%</div>
            <div class="sub">{_ft_label} upside potential</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Overlaid forecast chart ───────────────────────────────────────────
    # Aggregate across all cities
    _chart_color_cons = '#6C5CE7'
    agg = profit_fc.groupby(['created_at', 'scenario'])[
        _ft_metric
    ].sum().reset_index()

    fig_fc = go.Figure()

    for scenario in ['Conservative Growth', 'Aggressive Growth']:
        sdata = agg[agg['scenario'] == scenario]
        color = _chart_color_cons if scenario == 'Conservative Growth' else '#00B894'

        # Add confidence band (simulated as ±5% for conservative, ±8% for aggressive)
        band_pct = 0.05 if 'Conservative' in scenario else 0.08
        upper = sdata[_ft_metric] * (1 + band_pct)
        lower = sdata[_ft_metric] * (1 - band_pct)

        fig_fc.add_trace(go.Scatter(
            x=sdata['created_at'],
            y=sdata[_ft_metric],
            mode='lines',
            name=scenario,
            line=dict(color=color, width=2.5),
            hovertemplate=f'<b>%{{x|%b %d}}</b><br>{_ft_label}: {cur_sym()} %{{y:,.0f}}<br>',
        ))

        # Add confidence band
        fig_fc.add_trace(go.Scatter(
            x=pd.concat([sdata['created_at'], sdata['created_at'][::-1]]),
            y=pd.concat([upper, lower[::-1]]),
            fill='toself',
            fillcolor=hex_to_rgba(color, 0.12),
            line=dict(width=0),
            showlegend=False,
            name=f'{scenario} range',
            hoverinfo='skip',
        ))

    # Add a "Forecast Start" marker line
    fig_fc.add_shape(
        type='line',
        x0='2025-07-01', x1='2025-07-01',
        y0=0, y1=1,
        yref='paper',
        line=dict(dash='dash', color='#E17055', width=1.5),
    )
    fig_fc.add_annotation(
        x='2025-07-01',
        y=1, yref='paper',
        text='Forecast Start',
        showarrow=False,
        font=dict(color='#E17055', size=12),
        yshift=10,
    )

    fig_fc.update_layout(
        title=f'Projected {_ft_label} — Next 90 Days',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=CT['font'],
        xaxis=dict(showgrid=False, color=CT['axis'], title=''),
        yaxis=dict(showgrid=True, gridcolor=CT['grid'], color=CT['axis'], title=f'Daily {_ft_label} ({cur_sym()})'),
        legend=dict(font=dict(color=CT['legend']), orientation='h', y=1.08),
        margin=dict(l=40, r=20, t=50, b=40),
        hovermode='x unified',
        height=500,
    )
    st.plotly_chart(fig_fc, width='stretch')

    # ── Branch-level breakdown ────────────────────────────────────────────
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<h4>📍 Branch-Level Forecast</h4>', unsafe_allow_html=True)

    branch_agg = profit_fc.groupby(['branch', 'scenario'])[
        _ft_metric
    ].sum().reset_index()

    branch_pivot = branch_agg.pivot(
        index='branch', columns='scenario', values=_ft_metric
    ).reset_index()
    branch_pivot['Difference'] = (
        branch_pivot.get('Aggressive Growth', 0) - branch_pivot.get('Conservative Growth', 0)
    )
    _sym = cur_sym()
    branch_pivot.columns = ['Branch', f'Conservative Growth ({_sym})', f'Aggressive Growth ({_sym})', f'Difference ({_sym})']
    branch_pivot[f'Conservative Growth ({_sym})'] = branch_pivot[f'Conservative Growth ({_sym})'].apply(lambda x: currency(x, ',.0f'))
    branch_pivot[f'Aggressive Growth ({_sym})'] = branch_pivot[f'Aggressive Growth ({_sym})'].apply(lambda x: currency(x, ',.0f'))
    branch_pivot[f'Difference ({_sym})'] = branch_pivot[f'Difference ({_sym})'].apply(lambda x: currency(x, ',.0f'))

    st.dataframe(branch_pivot, hide_index=True, width='stretch')

    # ── Selected bundle impact (if any) ────────────────────────────────────
    if st.session_state.selected_bundle:
        st.markdown('<hr>', unsafe_allow_html=True)
        st.markdown(
            f'<h4>📦 Bundle Impact: {st.session_state.selected_bundle}</h4>',
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div style="color:#888;">Switch to <strong>Bundle Intelligence</strong> tab to explore bundle details, '
            'or click a different bundle below:</div>',
            unsafe_allow_html=True
        )

        # Allow quick bundle change
        col_clear, _ = st.columns([1, 3])
        with col_clear:
            if st.button('🔄 Clear Bundle Selection', width='stretch'):
                st.session_state.selected_bundle = None
                st.rerun()


def render_explorer():
    """🔬 Strategic Explorer — scenario planning with interactive sliders."""

    st.markdown('<h2>🔬 Strategic Explorer</h2>', unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#888;margin-bottom:16px;">'
        'Adjust strategy levers and see how your profit and inventory turnover would change. '
        'This is a <strong>cause-and-effect simulator</strong> — not a crystal ball.</div>',
        unsafe_allow_html=True
    )

    # ── Scenario Parameters ───────────────────────────────────────────────
    st.markdown('<h4>🎛️ Strategy Levers</h4>', unsafe_allow_html=True)

    col_s1, col_s2, col_s3 = st.columns(3)

    with col_s1:
        price_adj = st.slider(
            'Price Adjustment',
            -20, 20, 0, 1,
            format='%d%%',
            help='Increase or decrease menu prices across the board',
        ) / 100.0

    with col_s2:
        stock_adj = st.slider(
            'Stock Levels',
            -50, 50, 0, 5,
            format='%d%%',
            help='Adjust inventory availability (affects stock turnover)',
        ) / 100.0

    with col_s3:
        discount_intensity = st.slider(
            'Discount Intensity',
            0, 40, 0, 5,
            format='%d%%',
            help='How aggressively to offer discounts and promotions',
        ) / 100.0

    # ── Calculate scenario impacts ────────────────────────────────────────
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<h4>📊 Scenario Impact Analysis</h4>', unsafe_allow_html=True)

    # Base values from financial engine
    base_margin = fin_engine.get_net_margin('Latte')
    base_price = base_margin['price']
    base_net = base_margin['net_profit']

    # Simulate price elasticity: price increase reduces volume, price decrease increases volume
    # Elasticity estimate for coffee: ~-0.5 (inelastic)
    ELASTICITY = -0.5
    volume_impact = 1 + (price_adj * ELASTICITY)

    # New price and net margin
    new_price = base_price * (1 + price_adj)
    new_cogs = base_margin['cogs']  # COGS doesn't change with price
    new_op_cost = base_margin['operating_cost']
    new_discount = base_price * discount_intensity  # Discount on original price
    new_net = new_price - new_cogs - new_op_cost - new_discount

    # Impact on volume
    base_transactions = 2000  # Approximate daily avg per branch

    # Stock level impact: more stock = higher availability = more sales (diminishing)
    stock_sales_boost = stock_adj * 0.3  # 30% pass-through

    # Discount impact: higher discount drives more volume (but lower margin per unit)
    discount_volume_boost = discount_intensity * 1.2  # 120% pass-through (promotional elasticity)

    # Net volume impact
    total_volume_factor = volume_impact * (1 + stock_sales_boost) * (1 + discount_volume_boost)

    # ── Display scenario results ──────────────────────────────────────────
    res1, res2, res3, res4 = st.columns(4)

    price_change_pct = price_adj * 100
    with res1:
        if price_change_pct >= 0:
            delta = f"+{price_change_pct:.0f}%"
        else:
            delta = f"{price_change_pct:.0f}%"
        st.markdown(f"""
        <div class="insight-card">
            <h4>Price Change</h4>
            <div class="value" style="color:#6C5CE7;">{delta}</div>
            <div class="sub">Base price: {currency(base_price, ',.0f')} → {currency(new_price, ',.0f')}</div>
        </div>
        """, unsafe_allow_html=True)

    with res2:
        net_change = new_net - base_net
        net_change_pct = (net_change / base_net * 100) if base_net > 0 else 0
        st.markdown(f"""
        <div class="insight-card">
            <h4>Profit per Transaction</h4>
            <div class="value" style="color:#{'00B894' if net_change >= 0 else 'E17055'};">
                {currency(new_net, ',.2f')}
            </div>
            <div class="sub">Change: {net_change_pct:+.1f}%</div>
        </div>
        """, unsafe_allow_html=True)

    with res3:
        vol_change_pct = (total_volume_factor - 1) * 100
        st.markdown(f"""
        <div class="insight-card">
            <h4>Transaction Volume</h4>
            <div class="value" style="color:#{'00B894' if vol_change_pct >= 0 else 'E17055'};">
                {vol_change_pct:+.1f}%
            </div>
            <div class="sub">Estimated change in daily transactions</div>
        </div>
        """, unsafe_allow_html=True)

    with res4:
        # Total profit impact = new_net_per_unit * new_volume
        new_total_per_unit = new_net
        base_total_per_unit = base_net
        total_profit_change = (new_total_per_unit * total_volume_factor - base_total_per_unit) / base_total_per_unit * 100 if base_total_per_unit > 0 else 0
        st.markdown(f"""
        <div class="insight-card">
            <h4>Overall Profit Impact</h4>
            <div class="value" style="color:#{'00B894' if total_profit_change >= 0 else 'E17055'};">
                {total_profit_change:+.1f}%
            </div>
            <div class="sub">Net effect of all strategy changes</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr>', unsafe_allow_html=True)

    # ── Cause-and-effect waterfall ────────────────────────────────────────
    st.markdown('<h4>🔄 Cause & Effect Breakdown</h4>', unsafe_allow_html=True)

    # Build waterfall
    base_total = 100.0  # Indexed
    price_effect = price_adj * 100 * 0.6  # Price has ~60% pass-through to profit
    volume_effect_elasticity = (volume_impact - 1) * 100
    stock_effect = stock_sales_boost * 100
    discount_volume_effect = discount_volume_boost * 100
    discount_margin_effect = -discount_intensity * 100 * 0.8  # Discount erodes margin

    waterfall = go.Figure(go.Waterfall(
        name='Impact',
        orientation='v',
        measure=['relative', 'relative', 'relative', 'relative', 'total'],
        x=[
            'Price Change',
            'Volume Elasticity',
            'Stock Availability',
            'Discount Strategy',
            'Net Impact',
        ],
        y=[
            price_effect,
            volume_effect_elasticity,
            stock_effect,
            discount_margin_effect,
            base_total + price_effect + volume_effect_elasticity + stock_effect + discount_margin_effect,
        ],
        text=[
            f'{price_effect:+.1f}%',
            f'{volume_effect_elasticity:+.1f}%',
            f'{stock_effect:+.1f}%',
            f'{discount_margin_effect:+.1f}%',
            f'{base_total + price_effect + volume_effect_elasticity + stock_effect + discount_margin_effect:.1f}%',
        ],
        textposition='outside',
        connector={'line': {'color': CT['grid'], 'width': 1}},
        decreasing={'marker': {'color': '#E17055'}},
        increasing={'marker': {'color': '#00B894'}},
        totals={'marker': {'color': '#6C5CE7'}},
    ))
    waterfall.update_layout(
        title='How Each Lever Affects Overall Profit (Indexed to 100%)',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=CT['font'],
        xaxis=dict(showgrid=False, color=CT['axis']),
        yaxis=dict(showgrid=True, gridcolor=CT['grid'], color=CT['axis'], title='Profit Impact (%)'),
        margin=dict(l=40, r=40, t=50, b=40),
        height=450,
        showlegend=False,
    )
    st.plotly_chart(waterfall, width='stretch')

    # ── Sensitivity matrix: Price vs Discount ─────────────────────────────
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<h4>📈 Price-Discount Sensitivity Matrix</h4>', unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#888;margin-bottom:12px;">'
        'See how different price & discount combinations affect total profit. '
        'Darker green = higher profit.</div>',
        unsafe_allow_html=True
    )

    # Build heatmap
    price_range = np.arange(-0.20, 0.21, 0.05)
    discount_range = np.arange(0, 0.41, 0.05)

    sensitivity = np.zeros((len(discount_range), len(price_range)))

    for i, d in enumerate(discount_range):
        for j, p in enumerate(price_range):
            vol = 1 + (p * ELASTICITY) * (1 + d * 1.2)
            np_ = base_price * (1 + p)
            nd = base_price * d
            np_net = np_ - base_margin['cogs'] - base_margin['operating_cost'] - nd
            total_idx = (np_net * vol) / base_net * 100 if base_net > 0 else 0
            sensitivity[i, j] = total_idx

    fig_heat = px.imshow(
        sensitivity,
        x=[f'{p*100:.0f}%' for p in price_range],
        y=[f'{d*100:.0f}%' for d in discount_range],
        color_continuous_scale='RdYlGn',
        labels={'x': 'Price Adjustment', 'y': 'Discount Intensity', 'color': 'Profit Index'},
        title='Total Profit Index (100 = baseline)',
        aspect='auto',
        text_auto='.0f',
    )
    fig_heat.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=CT['font'],
        xaxis=dict(color=CT['axis']),
        yaxis=dict(color=CT['axis']),
        coloraxis_colorbar=dict(
            tickfont=dict(color=CT['font']),
            title_font=dict(color=CT['font']),
        ),
        margin=dict(l=40, r=40, t=50, b=40),
        height=400,
    )
    st.plotly_chart(fig_heat, width='stretch')

    # ── Strategic Recommendation ──────────────────────────────────────────
    st.markdown('<hr>', unsafe_allow_html=True)
    st.markdown('<h4>💡 Strategy Insight</h4>', unsafe_allow_html=True)

    # Generate a textual insight based on current slider positions
    if total_profit_change > 10:
        verdict = '🟢 Strong positive impact'
        detail = 'Your current strategy settings show significant profit potential. Consider piloting these changes in high-traffic branches first.'
    elif total_profit_change > 2:
        verdict = '🔵 Moderate improvement'
        detail = 'These adjustments show modest profit gains. Fine-tune individual levers to optimize further.'
    elif total_profit_change > -2:
        verdict = '⚪ Neutral impact'
        detail = 'The combined effect is near baseline. Try more aggressive adjustments or focus on specific bundles.'
    elif total_profit_change > -10:
        verdict = '🟡 Caution — negative impact'
        detail = 'Current settings reduce profitability. Consider reducing discounts or adjusting prices more conservatively.'
    else:
        verdict = '🔴 Significant risk'
        detail = 'These settings would substantially reduce profit. Revisit your assumptions and try more moderate adjustments.'

    st.markdown(f"""
    <div class="insight-card">
        <h4>{verdict}</h4>
        <div style="color:#E0E0E0;font-size:1rem;">{detail}</div>
        <div class="sub" style="margin-top:8px;">
            Price: {price_adj*100:+.0f}% · Stock: {stock_adj*100:+.0f}% · Discount: {discount_intensity*100:.0f}% ·
            Est. profit impact: {total_profit_change:+.1f}%
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Save scenario ─────────────────────────────────────────────────────
    st.markdown('<br>', unsafe_allow_html=True)
    if st.button('💾 Save This Scenario'):
        st.session_state.scenario_params = {
            'price_adj': price_adj,
            'stock_level': stock_adj,
            'discount_intensity': discount_intensity,
        }
        st.success('Scenario saved! Switch between tabs to compare.')


# ══════════════════════════════════════════════════════════════════════════════
#  AI ANALYST TAB
# ══════════════════════════════════════════════════════════════════════════════

def render_ai_analyst():
    """🤖 AI Analyst — natural language insights via Groq (gratis)."""

    st.markdown('<h2>🤖 AI Business Analyst</h2>', unsafe_allow_html=True)
    st.markdown(
        '<div style="color:#888;margin-bottom:8px;">'
        'Tanya apapun tentang bisnis — AI akan jawab berdasarkan data real.</div>',
        unsafe_allow_html=True,
    )

    if not gemini.is_ready:
        st.info(
            "🔑 **Set API Key Groq**\n\n"
            "1. Buka https://aistudio.google.com/apikey\n"
            "2. Buat API key (gratis)\n"
            "3. Set environment variable:\n"
            "   ```powershell\n"
            '   $env:GEMINI_API_KEY = "AIza..."\n'
            "   ```\n"
            "   Atau restart terminal, lalu jalankan ulang app."
        )
        return

    # ── Filter sidebar-style in-page ───────────────────────────────────────
    col_f1, col_f2, col_f3 = st.columns(3)

    with col_f1:
        seg_list = sorted(seg_counts["segment"].unique().tolist())
        sel_seg = st.selectbox("Target Segmen", seg_list, key="ai_segment")

    with col_f2:
        branch_list = sorted(
            load_historical_daily()["city"].unique().tolist()
        )
        sel_branch = st.selectbox("Cabang", branch_list, key="ai_branch")

    with col_f3:
        day_type = st.radio("Tipe Hari", ["Weekday", "Weekend"], horizontal=True, key="ai_day")

    # ── Chat input ─────────────────────────────────────────────────────────
    st.markdown('<hr>', unsafe_allow_html=True)

    # Suggested questions
    st.markdown(
        '<div style="font-size:0.85rem;margin-bottom:8px;">'
        "Coba tanya:</div>",
        unsafe_allow_html=True,
    )
    suggestions = [
        "Rekomendasi voucher apa yang tepat untuk segmen ini?",
        "Bundle produk apa yang cocok?",
        "Apa insight utama dari data ini?",
        "Custom...",
    ]
    cols = st.columns(4)
    for i, suggestion in enumerate(suggestions):
        with cols[i]:
            if st.button(suggestion, key=f"ai_sug_{i}", width="stretch"):
                st.session_state["ai_question"] = suggestion if suggestion != "Custom..." else ""
                st.rerun()

    # Free text input
    question = st.text_input(
        "✏️ Atau tulis pertanyaan sendiri:",
        key="ai_question",
        placeholder="Contoh: Rekomendasi bundling untuk Matcha Latte di USJ?",
        label_visibility="collapsed",
    )

    st.markdown('<br>', unsafe_allow_html=True)

    # ── Generate insight ───────────────────────────────────────────────────
    if question:
        with st.spinner("🧠 Menganalisis data..."):
            # Build context data dari engine yang sudah ada
            context_json = build_context(
                segment_name=sel_seg,
                seg_counts=seg_counts,
                branch_name=sel_branch,
                day_type=day_type,
                rules_df=rules_df,
                menu_df=menu_df,
                fin_engine=fin_engine,
                fc_engine=fc_engine,
                question=question,
                currency=st.session_state.get('currency', 'RM'),
            )

            # Panggil Groq (cache 5 menit)
            insight = gemini.analyze(context_json)

        # ── Display insight ────────────────────────────────────────────────
        st.markdown("### 💡 Hasil Analisis")
        st.markdown(
            f'<div class="insight-card" style="line-height:1.7;">{insight}</div>',
            unsafe_allow_html=True,
        )

        # ── Show context data (expandable) ─────────────────────────────────
        with st.expander("📦 Lihat data yang dikirim ke AI"):
            st.code(context_json, language="json")
            st.caption("Data ini 100% dari engine — AI (Groq) hanya merangkai.")

    else:
        st.markdown(
            '<div style="color:#666;text-align:center;padding:40px;">'
            "☝️ Pilih pertanyaan di atas atau tulis sendiri</div>",
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ROUTER
# ══════════════════════════════════════════════════════════════════════════════

# ── Theme toggle icon button (top-right, absolutely positioned via CSS) ──
_icon = '☀️' if _effective_theme == 'dark' else '🌙'
_help = 'Switch to Light Mode' if _effective_theme == 'dark' else 'Switch to Dark Mode'
if st.button(_icon, key='theme_btn', help=_help):
    st.session_state.theme_toggle = '☀️ Light' if _effective_theme == 'dark' else '🌙 Dark'
    st.rerun()

# ── Analytical Lens Switcher ───────────────────────────────────────────────
_lens_holder = st.empty()
with _lens_holder.container():
    lens_col1, lens_col2 = st.columns([1, 4])
    with lens_col1:
        st.markdown('<div style="font-size:0.85rem;font-weight:500;color:var(--txt-secondary);padding-top:6px;">🎯 Focus:</div>', unsafe_allow_html=True)
    with lens_col2:
        _lens = st.radio(
            "Analytical Lens",
            ["💰 Profit", "📈 Revenue"],
            index=0 if st.session_state.dashboard_lens == 'Profit' else 1,
            horizontal=True,
            label_visibility="collapsed",
            key="lens_radio",
        )
        st.session_state.dashboard_lens = 'Revenue' if 'Revenue' in _lens else 'Profit'

if selected_tab == nav_tabs[0]:
    render_overview()
elif selected_tab == nav_tabs[1]:
    render_segments()
elif selected_tab == nav_tabs[2]:
    render_bundles()
elif selected_tab == nav_tabs[3]:
    render_forecast()
elif selected_tab == nav_tabs[4]:
    render_explorer()
elif selected_tab == nav_tabs[5]:
    render_ai_analyst()

# ══════════════════════════════════════════════════════════════════════════════
#  FOOTER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<hr style="border-color:#2D3142;">', unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:#555;font-size:0.75rem;padding:8px;">'
    'G Coffee Shop · Strategic Intelligence Dashboard · Prescriptive Analytics v2.0</div>',
    unsafe_allow_html=True
)
