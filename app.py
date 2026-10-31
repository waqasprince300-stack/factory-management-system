"""
Threadworks — Embroidery Factory Production & Costing ERP
Separate Systems for:
1. Dhaaga (Thread / Cones) Calculation
2. Stitch & 1 Piece Rate Calculation (per 1,000 stitches)
Complete Roman Urdu Interface for Pakistani Embroidery Factory Operations.
"""

import hashlib
import math
import re
import pandas as pd
import streamlit as st
import importlib

# Reload core modules so updates in core/ are always fresh without restarting server
import core.config
import core.security
import core.parser
import core.calculator

importlib.reload(core.config)
importlib.reload(core.security)
importlib.reload(core.parser)
importlib.reload(core.calculator)

from core.config import (
    DEFAULT_MACHINE_HEADS,
    DEFAULT_BASE_COLORS,
    DEFAULT_WASTAGE_PCT,
    DEFAULT_CONE_CAPACITY_METERS,
    DEFAULT_CONE_CAPACITY_YARDS,
    DEFAULT_STITCH_RATE,
    DEFAULT_CONE_PRICE,
    DEFAULT_MACHINE_RPM,
    DEFAULT_SHIFT_HOURS,
    METERS_TO_YARDS,
    DOUBLE_HEAD_WIDTH_THRESHOLD_MM
)
from core.security import validate_uploaded_file
from core.parser import parse_wilcom_pdf, parse_image_part, extract_repeat_from_text, extract_dual_shade
from core.calculator import (
    aggregate_suit_parts,
    calculate_full_production,
    compute_part_heads_config,
    get_part_mode_options,
    is_same_color
)

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Threadworks • Factory Embroidery Calculator",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE & THEME PERSISTENCE
# ═══════════════════════════════════════════════════════════════════════════
url_theme = st.query_params.get("theme", "").strip().lower()
persisted_theme = "Light" if url_theme == "light" else "Dark"

if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = persisted_theme

def _safe_int_param(key, default_val, min_v, max_v):
    try:
        if key in st.query_params:
            return max(min_v, min(max_v, int(st.query_params[key])))
    except Exception:
        pass
    return default_val

def _safe_float_param(key, default_val, min_v, max_v):
    try:
        if key in st.query_params:
            return max(min_v, min(max_v, float(st.query_params[key])))
    except Exception:
        pass
    return default_val

if "saved_heads" not in st.session_state:
    st.session_state.saved_heads = _safe_int_param("heads", DEFAULT_MACHINE_HEADS, 1, 120)

if "saved_lots" not in st.session_state:
    st.session_state.saved_lots = _safe_float_param("lots", 1.0, 0.5, 50.0)

if "saved_shades" not in st.session_state:
    st.session_state.saved_shades = _safe_int_param("shades", DEFAULT_BASE_COLORS, 1, 30)

if "saved_waste" not in st.session_state:
    st.session_state.saved_waste = _safe_float_param("waste", 0.0, 0.0, 30.0)

if "saved_rate" not in st.session_state:
    st.session_state.saved_rate = _safe_float_param("rate", DEFAULT_STITCH_RATE, 0.05, 10.0)

if "suit_design_name" not in st.session_state:
    st.session_state.suit_design_name = ""

if "parts" not in st.session_state:
    st.session_state.parts = {}

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if "custom_same_overrides" not in st.session_state:
    st.session_state.custom_same_overrides = {}

is_dark = (st.session_state.theme_mode == "Dark")

# ═══════════════════════════════════════════════════════════════════════════
# MODERN DESIGN SYSTEM (VANILLA CSS)
# ═══════════════════════════════════════════════════════════════════════════
if is_dark:
    theme_css_vars = """
    :root {
        --primary-color: #f59e0b;
        --background-color: #0b0f19;
        --secondary-background-color: #111827;
        --text-color: #f8fafc;
        --bg-main: #0b0f19;
        --bg-surface: #111827;
        --bg-surface-elevated: #1e293b;
        --bg-surface-subtle: #162032;
        --border-main: #27354f;
        --border-focus: #f59e0b;
        --border-subtle: #1e293b;
        --text-primary: #f8fafc;
        --text-secondary: #cbd5e1;
        --text-muted: #94a3b8;
        --label-color: #f1f5f9;
        --input-bg: #0f172a;
        --input-border: #334155;
        --btn-bg: #1e293b;
        --btn-border: #384860;
        --btn-text: #f8fafc;
        --btn-hover-bg: #2d3b55;
        --btn-hover-border: #f59e0b;
        --btn-hover-text: #ffffff;
        --table-header-bg: #162032;
        --table-row-hover: #1e293b;
        --table-cell-border: #1e293b;
        --tab-active-bg: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(192, 132, 252, 0.15));
        --accent-amber: #f59e0b;
        --accent-purple: #c084fc;
        --accent-cyan: #38bdf8;
        --accent-green: #10b981;
        --accent-pink: #f472b6;
        --accent-coral: #fb923c;
        --card-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
        --card-hover-shadow: 0 8px 24px rgba(245, 158, 11, 0.18);
    }
    """
else:
    theme_css_vars = """
    :root {
        --primary-color: #d97706;
        --background-color: #f8fafc;
        --secondary-background-color: #ffffff;
        --text-color: #0f172a;
        --bg-main: #f8fafc;
        --bg-surface: #ffffff;
        --bg-surface-elevated: #f1f5f9;
        --bg-surface-subtle: #f8fafc;
        --border-main: #e2e8f0;
        --border-focus: #d97706;
        --border-subtle: #edf2f7;
        --text-primary: #0f172a;
        --text-secondary: #475569;
        --text-muted: #64748b;
        --label-color: #0f172a;
        --input-bg: #ffffff;
        --input-border: #cbd5e1;
        --btn-bg: #f8fafc;
        --btn-border: #cbd5e1;
        --btn-text: #0f172a;
        --btn-hover-bg: #f1f5f9;
        --btn-hover-border: #d97706;
        --btn-hover-text: #0f172a;
        --table-header-bg: #f1f5f9;
        --table-row-hover: #f8fafc;
        --table-cell-border: #e2e8f0;
        --tab-active-bg: #fef3c7;
        --accent-amber: #d97706;
        --accent-purple: #7c3aed;
        --accent-cyan: #0284c7;
        --accent-green: #059669;
        --accent-pink: #db2777;
        --accent-coral: #ea580c;
        --card-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
        --card-hover-shadow: 0 8px 20px rgba(217, 119, 6, 0.12);
    }
    """

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700;800&display=swap');

{theme_css_vars}

html, body, [class*="css"], .stApp {{
    background-color: var(--bg-main) !important;
    color: var(--text-primary) !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
    letter-spacing: -0.01em;
}}

/* Header Banner */
.brand-header {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 12px;
    padding: 12px 18px;
    margin-bottom: 12px;
    box-shadow: var(--card-shadow);
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
}}
.brand-title-box {{
    display: flex;
    align-items: center;
    gap: 12px;
}}
.brand-logo-icon {{
    font-size: 1.8rem;
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(192, 132, 252, 0.2));
    border: 1px solid var(--border-main);
    border-radius: 10px;
    padding: 4px 10px;
}}
.brand-main-text {{
    font-size: 1.25rem;
    font-weight: 800;
    color: var(--text-primary);
    line-height: 1.2;
}}
.brand-sub-text {{
    font-size: 0.82rem;
    color: var(--text-secondary);
    font-weight: 500;
    margin-top: 2px;
}}
.brand-pill {{
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-main);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--text-secondary);
    display: inline-flex;
    align-items: center;
    gap: 6px;
}}
.brand-pill strong {{
    color: var(--text-primary);
}}

/* Top Settings Card */
.settings-panel {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 12px;
    box-shadow: var(--card-shadow);
}}
.panel-title {{
    font-size: 0.82rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--accent-amber);
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 6px;
}}

/* KPI Metric Cards Grid */
.kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 10px;
    margin-bottom: 14px;
}}
.kpi-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 10px;
    padding: 12px 14px;
    box-shadow: var(--card-shadow);
    transition: all 0.2s ease;
    position: relative;
    overflow: hidden;
}}
.kpi-card:hover {{
    transform: translateY(-2px);
    box-shadow: var(--card-hover-shadow);
    border-color: var(--border-focus);
}}
.kpi-card::before {{
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    width: 4px;
    height: 100%;
}}
.kpi-card.purple::before {{ background: var(--accent-purple); }}
.kpi-card.amber::before {{ background: var(--accent-amber); }}
.kpi-card.cyan::before {{ background: var(--accent-cyan); }}
.kpi-card.green::before {{ background: var(--accent-green); }}
.kpi-card.pink::before {{ background: var(--accent-pink); }}
.kpi-card.coral::before {{ background: var(--accent-coral); }}

.kpi-label {{
    font-size: 0.78rem;
    font-weight: 800;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 4px;
}}
.kpi-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.55rem;
    font-weight: 900;
    line-height: 1.2;
    margin-bottom: 3px;
}}
.kpi-subtext {{
    font-size: 0.78rem;
    color: var(--text-secondary);
    font-weight: 700;
}}

@media (max-width: 768px) {{
    .kpi-grid {{
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 8px !important;
    }}
    .kpi-card {{
        padding: 10px 12px !important;
    }}
    .kpi-value {{
        font-size: 1.25rem !important;
    }}
    .kpi-subtext {{
        font-size: 0.72rem !important;
    }}
    .brand-header {{
        padding: 10px 12px !important;
    }}
    .brand-main-text {{
        font-size: 1.05rem !important;
    }}
    .brand-pill {{
        padding: 3px 8px !important;
        font-size: 0.72rem !important;
    }}
    .part-card {{
        padding: 10px 12px !important;
    }}
}}
@media (max-width: 480px) {{
    .kpi-grid {{
        grid-template-columns: 1fr !important;
    }}
}}

/* Part Cut-Sheet Card */
.part-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 10px;
    padding: 14px 16px;
    margin-bottom: 10px;
    box-shadow: var(--card-shadow);
    transition: border-color 0.2s ease;
}}
.part-card:hover {{
    border-color: var(--border-focus);
}}

/* Badges */
.badge-tag {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 6px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}}
.badge-tag.standard {{
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.35);
    color: var(--accent-cyan);
}}
.badge-tag.double {{
    background: rgba(245, 158, 11, 0.12);
    border: 1px solid rgba(245, 158, 11, 0.35);
    color: var(--accent-amber);
}}
.badge-tag.multi {{
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.35);
    color: var(--accent-green);
}}
.badge-tag.same {{
    background: rgba(192, 132, 252, 0.14);
    border: 1px solid rgba(192, 132, 252, 0.35);
    color: var(--accent-purple);
}}

/* Custom Table Styling */
.table-container {{
    border: 1px solid var(--border-main);
    border-radius: 10px;
    overflow-x: auto;
    background: var(--bg-surface);
    margin-bottom: 12px;
}}
.modern-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    text-align: left;
}}
.modern-table th {{
    background: var(--table-header-bg) !important;
    color: var(--accent-amber) !important;
    font-weight: 800 !important;
    text-transform: uppercase !important;
    font-size: 0.76rem !important;
    letter-spacing: 0.04em !important;
    padding: 11px 12px !important;
    border-bottom: 1.5px solid var(--border-main) !important;
}}
.modern-table td {{
    padding: 9px 12px;
    border-bottom: 1px solid var(--table-cell-border);
    color: var(--text-primary);
}}
.modern-table tr:hover {{
    background: var(--table-row-hover);
}}

/* Streamlit Widget Polishing */
div[data-testid="stTextInput"] input,
div[data-testid="stNumberInput"] input {{
    background-color: var(--input-bg) !important;
    border: 1px solid var(--input-border) !important;
    border-radius: 7px !important;
    color: var(--text-primary) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
}}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stNumberInput"] input:focus {{
    border-color: var(--border-focus) !important;
    box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.25) !important;
}}

/* Stepper +/- buttons in stNumberInput */
div[data-testid="stNumberInput"] button,
div[data-testid="stNumberInputStepDown"],
div[data-testid="stNumberInputStepUp"] {{
    background-color: var(--bg-surface-elevated) !important;
    border-color: var(--input-border) !important;
    color: var(--text-primary) !important;
}}
div[data-testid="stNumberInput"] button:hover,
div[data-testid="stNumberInputStepDown"]:hover,
div[data-testid="stNumberInputStepUp"]:hover {{
    background-color: var(--btn-hover-bg) !important;
    color: var(--accent-amber) !important;
    border-color: var(--border-focus) !important;
}}
div[data-testid="stNumberInput"] button svg {{
    fill: var(--text-primary) !important;
}}

/* BaseWeb Selectbox & Dropdown Menus */
.stApp [data-testid="stSelectbox"] [data-baseweb="select"],
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div,
.stApp [data-baseweb="select"],
.stApp [data-baseweb="select"] > div {{
    background-color: var(--input-bg) !important;
    border: 1px solid var(--input-border) !important;
    border-radius: 7px !important;
}}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] > div:hover,
.stApp [data-baseweb="select"] > div:hover {{
    border-color: var(--border-focus) !important;
}}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] span,
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] div,
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] input,
.stApp [data-baseweb="select"] span,
.stApp [data-baseweb="select"] div,
.stApp [data-baseweb="select"] input {{
    color: var(--text-primary) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.85rem !important;
    font-weight: 700 !important;
}}
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] svg,
.stApp [data-baseweb="select"] svg {{
    fill: var(--text-primary) !important;
    color: var(--text-primary) !important;
}}
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
ul[role="listbox"] {{
    background-color: var(--bg-surface-elevated) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    box-shadow: var(--card-shadow) !important;
}}
li[role="option"] {{
    background-color: transparent !important;
    color: var(--text-primary) !important;
    font-size: 0.84rem !important;
    font-weight: 600 !important;
    padding: 8px 12px !important;
}}
li[role="option"]:hover,
li[role="option"][aria-selected="true"] {{
    background-color: var(--table-row-hover) !important;
    color: var(--accent-amber) !important;
}}

/* High-Contrast Widget Labels */
.stApp [data-testid="stWidgetLabel"],
.stApp [data-testid="stWidgetLabel"] *,
.stApp [data-testid="stWidgetLabel"] label,
.stApp [data-testid="stWidgetLabel"] p,
.stApp [data-testid="stWidgetLabel"] span,
.stApp [data-testid="stWidgetLabel"] div {{
    color: var(--label-color) !important;
    font-weight: 800 !important;
    font-size: 0.77rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.04em !important;
}}
.stApp [data-testid="stWidgetLabel"] svg {{
    fill: var(--text-muted) !important;
}}

/* Button System */
.stButton > button,
button[kind="primary"],
button[kind="secondary"],
div[data-testid="stDownloadButton"] > button {{
    background-color: var(--btn-bg) !important;
    color: var(--btn-text) !important;
    border: 1px solid var(--btn-border) !important;
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: 0.84rem !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2) !important;
    transition: all 0.15s ease !important;
}}
.stButton > button:hover,
button[kind="primary"]:hover,
button[kind="secondary"]:hover,
div[data-testid="stDownloadButton"] > button:hover {{
    background-color: var(--btn-hover-bg) !important;
    color: var(--btn-hover-text) !important;
    border-color: var(--border-focus) !important;
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.2) !important;
}}

/* Specialized Toolbar Buttons */
.demo-btn-wrap .stButton > button {{
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.16), rgba(192, 132, 252, 0.16)) !important;
    border: 1px solid var(--accent-amber) !important;
    color: var(--accent-amber) !important;
    font-weight: 800 !important;
}}
.demo-btn-wrap .stButton > button:hover {{
    background: linear-gradient(135deg, rgba(245, 158, 11, 0.28), rgba(192, 132, 252, 0.28)) !important;
    box-shadow: 0 4px 14px rgba(245, 158, 11, 0.25) !important;
    color: #ffffff !important;
    border-color: #f59e0b !important;
}}
.clear-btn-wrap .stButton > button {{
    background-color: rgba(239, 68, 68, 0.1) !important;
    border: 1px solid rgba(239, 68, 68, 0.35) !important;
    color: #f87171 !important;
    font-weight: 700 !important;
}}
.clear-btn-wrap .stButton > button:hover {{
    background-color: rgba(239, 68, 68, 0.24) !important;
    border-color: #ef4444 !important;
    color: #ffffff !important;
}}
.del-btn-wrap .stButton > button {{
    background-color: rgba(239, 68, 68, 0.15) !important;
    border: 1px solid rgba(239, 68, 68, 0.45) !important;
    color: #f87171 !important;
    border-radius: 8px !important;
    font-size: 1.15rem !important;
    padding: 6px !important;
    box-shadow: 0 1px 4px rgba(239, 68, 68, 0.15) !important;
}}
.del-btn-wrap .stButton > button:hover {{
    background-color: rgba(239, 68, 68, 0.35) !important;
    border-color: #ef4444 !important;
    color: #ffffff !important;
    box-shadow: 0 0 12px rgba(239, 68, 68, 0.4) !important;
}}

/* File Uploader */
.stApp div[data-testid="stFileUploader"] {{
    background: transparent !important;
}}
.stApp div[data-testid="stFileUploader"] section {{
    background-color: var(--bg-surface) !important;
    border: 1px dashed var(--border-main) !important;
    border-radius: 8px !important;
    padding: 10px 14px !important;
}}
.stApp div[data-testid="stFileUploader"] section:hover {{
    border-color: var(--border-focus) !important;
}}
.stApp div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] {{
    color: var(--text-secondary) !important;
}}
.stApp div[data-testid="stFileUploaderFile"] {{
    background-color: var(--bg-surface-elevated) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 6px !important;
    padding: 4px 8px !important;
}}
.stApp div[data-testid="stFileUploaderFileName"] {{
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-size: 0.8rem !important;
}}
.stApp div[data-testid="stFileUploaderFileData"] {{
    color: var(--text-muted) !important;
    font-size: 0.72rem !important;
}}
.stApp div[data-testid="stFileUploaderFile"] button {{
    color: var(--text-secondary) !important;
}}
.stApp div[data-testid="stFileUploaderFile"] button:hover {{
    color: #ef4444 !important;
}}
.stApp div[data-testid="stFileUploaderFile"] svg {{
    fill: var(--text-primary) !important;
}}

/* Radio Buttons Styling */
.stApp div[data-testid="stRadio"] > div {{
    gap: 12px;
}}
.stApp div[data-testid="stRadio"] label {{
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-size: 0.82rem !important;
}}
.stApp div[data-testid="stRadio"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {{
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    font-size: 0.82rem !important;
}}

/* Tab Styling */
.stApp .stTabs [data-baseweb="tab-list"] {{
    gap: 8px !important;
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 10px !important;
    padding: 6px !important;
}}
.stApp .stTabs [data-baseweb="tab"] {{
    background-color: var(--bg-surface-elevated) !important;
    border: 1px solid var(--border-subtle) !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    transition: all 0.2s ease !important;
}}
.stApp .stTabs [data-baseweb="tab"] p,
.stApp .stTabs [data-baseweb="tab"] span,
.stApp .stTabs [data-baseweb="tab"] div {{
    color: var(--text-secondary) !important;
    font-weight: 700 !important;
    font-size: 0.84rem !important;
}}
.stApp .stTabs [data-baseweb="tab"]:hover {{
    background-color: var(--btn-hover-bg) !important;
    border-color: var(--border-focus) !important;
}}
.stApp .stTabs [data-baseweb="tab"]:hover p,
.stApp .stTabs [data-baseweb="tab"]:hover span,
.stApp .stTabs [data-baseweb="tab"]:hover div {{
    color: var(--text-primary) !important;
}}
.stApp .stTabs [data-baseweb="tab"][aria-selected="true"] {{
    background: var(--tab-active-bg) !important;
    border: 1.5px solid var(--accent-amber) !important;
    box-shadow: 0 4px 12px rgba(245, 158, 11, 0.2) !important;
}}
.stApp .stTabs [data-baseweb="tab"][aria-selected="true"] p,
.stApp .stTabs [data-baseweb="tab"][aria-selected="true"] span,
.stApp .stTabs [data-baseweb="tab"][aria-selected="true"] div {{
    color: var(--accent-amber) !important;
    font-weight: 800 !important;
}}
.stApp .stTabs [data-baseweb="tab-highlight"],
.stApp .stTabs [data-baseweb="tab-border"] {{
    background-color: transparent !important;
}}
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# TOP HEADER & THEME TOGGLE
# ═══════════════════════════════════════════════════════════════════════════
col_hdr_main, col_hdr_theme = st.columns([8.2, 1.8])

with col_hdr_main:
    st.markdown(f"""
    <div class="brand-header">
        <div class="brand-title-box">
            <span class="brand-logo-icon">🧵</span>
            <div>
                <div class="brand-main-text">Threadworks — Factory Embroidery Master</div>
                <div class="brand-sub-text">Separate Systems: Dhaaga (Cones) Calculation & Stitch Rate (per 1,000 stitches)</div>
            </div>
        </div>
        <div>
            <span class="brand-pill">⚡ <strong>{st.session_state.saved_heads} Heads</strong></span>
            <span class="brand-pill">🎨 <strong>{st.session_state.saved_shades} Colors</strong></span>
            <span class="brand-pill">📦 <strong>{st.session_state.saved_lots:g} Lot</strong></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_hdr_theme:
    selected_theme = st.radio(
        "Theme",
        ["☀️ Light Mode", "🌙 Dark Mode"],
        index=0 if not is_dark else 1,
        horizontal=True,
        key="theme_toggle_radio",
        label_visibility="collapsed"
    )
    new_theme = "Dark" if "Dark" in selected_theme else "Light"
    if new_theme != st.session_state.theme_mode:
        st.session_state.theme_mode = new_theme
        st.query_params["theme"] = new_theme.lower()
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# MACHINE & ORDER SETTINGS PANEL (BUNYAADI SETTINGS)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown('<div class="panel-title">⚙️ Machine & Order Settings (Bunyaadi Settings)</div>', unsafe_allow_html=True)

cp1, cp2, cp3, cp4, cp5, cp6 = st.columns([1.6, 1.6, 2.4, 2.0, 1.4, 1.4])

with cp1:
    machine_heads = st.number_input(
        "Machine Heads (HEADS)",
        min_value=1,
        max_value=120,
        value=int(st.session_state.saved_heads),
        step=1,
        help="Machine heads (Default: 28 Heads)"
    )
    if machine_heads != st.session_state.saved_heads:
        st.session_state.saved_heads = machine_heads
        st.query_params["heads"] = str(machine_heads)
        st.rerun()

with cp2:
    base_colors_count = st.number_input(
        "Base Shades / Colors",
        min_value=1,
        max_value=30,
        value=int(st.session_state.saved_shades),
        step=1,
        help="Base cloth colors per lot (Default: 6 Colors)"
    )
    if base_colors_count != st.session_state.saved_shades:
        st.session_state.saved_shades = base_colors_count
        st.query_params["shades"] = str(base_colors_count)

pieces_per_lot = machine_heads * base_colors_count

with cp3:
    col_q_mode, col_q_val = st.columns([1.0, 1.4])
    with col_q_mode:
        lots_mode = st.radio("Lots ya Suits", ["Lots", "Suits"], index=0, horizontal=True)
    with col_q_val:
        if lots_mode == "Lots":
            lots_count = st.number_input(
                "Kul Lots (LOTS)",
                min_value=0.5,
                max_value=50.0,
                value=float(st.session_state.saved_lots),
                step=0.5,
                help="Total Lots (1 Lot = 28 Heads × 6 Colors = 168 Suits)"
            )
            if lots_count != st.session_state.saved_lots:
                st.session_state.saved_lots = lots_count
                st.query_params["lots"] = f"{lots_count:g}"
            num_pieces = int(round(pieces_per_lot * lots_count))
        else:
            num_pieces = st.number_input(
                "Kul Suits (SUITS)",
                min_value=1,
                max_value=100000,
                value=int(round(pieces_per_lot * st.session_state.saved_lots)),
                step=machine_heads
            )
            lots_count = round(num_pieces / pieces_per_lot, 2)

with cp4:
    col_u_type, col_u_val = st.columns([1.0, 1.4])
    with col_u_type:
        cone_unit = st.selectbox("Cone Unit", ["Meters", "Yards"], index=0)
    with col_u_val:
        default_cap = DEFAULT_CONE_CAPACITY_METERS if "Meters" in cone_unit else DEFAULT_CONE_CAPACITY_YARDS
        cone_capacity_val = st.number_input("Cone Size", min_value=100.0, max_value=50000.0, value=float(default_cap), step=100.0)

with cp5:
    waste_pct = st.number_input(
        "Dhaaga Wastage %",
        min_value=0.0,
        max_value=30.0,
        value=float(st.session_state.saved_waste),
        step=1.0,
        format="%.1f",
        help="Dhaaga wastage (Auto: 0%)"
    )
    if waste_pct != st.session_state.saved_waste:
        st.session_state.saved_waste = waste_pct
        st.query_params["waste"] = f"{waste_pct:.1f}"

with cp6:
    stitch_rate = st.number_input(
        "Stitch Rate (per 1,000)",
        min_value=0.05,
        max_value=10.0,
        value=float(st.session_state.saved_rate),
        step=0.05,
        format="%.2f",
        help="Rate per 1,000 stitches in PKR (Default: 1.45 Rs)"
    )
    if stitch_rate != st.session_state.saved_rate:
        st.session_state.saved_rate = stitch_rate
        st.query_params["rate"] = f"{stitch_rate:.2f}"

# Quick Summary Pill Bar
suits_per_color_calc = int(round(num_pieces / max(1, base_colors_count)))
st.markdown(f"""
<div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:8px; padding:6px 12px; font-size:0.78rem; color:var(--text-secondary); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:12px;">
    <span>📦 <strong>Kul Order:</strong> <span style="color:var(--text-primary); font-weight:700;">{num_pieces} Suits</span> ({lots_count:g} Lots)</span>
    <span>⚡ <strong>Machine:</strong> {machine_heads} Heads (1 Lot = {pieces_per_lot} Suits)</span>
    <span>🎨 <strong>Har Color k Suits:</strong> <span style="color:var(--accent-amber); font-weight:700;">{suits_per_color_calc} Suits</span> ({base_colors_count} Total Shades)</span>
    <span>🧵 <strong>Cone Size:</strong> {cone_capacity_val:,.0f} {cone_unit} (Wastage: {waste_pct:.0f}%)</span>
    <span>💵 <strong>Stitch Rate:</strong> <span style="color:var(--accent-green); font-weight:700;">Rs {stitch_rate:.2f}</span> / 1,000 stitches</span>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# FILE UPLOAD & CONTROLS TOOLBAR
# ═══════════════════════════════════════════════════════════════════════════
c_up_file, c_up_demo, c_up_clear = st.columns([6.8, 2.2, 1.0])

with c_up_file:
    uploaded_files = st.file_uploader(
        "Upload Wilcom PDF / Design Images:",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"file_uploader_{st.session_state.uploader_key}",
        label_visibility="collapsed"
    )

with c_up_demo:
    st.markdown('<div class="demo-btn-wrap">', unsafe_allow_html=True)
    if st.button("✨ Sample Suit Load Karein (Demo)", use_container_width=True, help="Front, Daman 4H, Sleeves 9H, Neck ka sample load karein"):
        st.session_state.suit_design_name = "Sample_Suit_D-101"
        st.session_state.parts = {
            "demo_front": {
                "design_name": "FRONT (Gala & Body)",
                "file_name": "Front_Gala.pdf",
                "stitches": 48500,
                "repeat": 1.0,
                "mode": "1_rep_all",
                "heads": machine_heads,
                "sequins_total": 0,
                "total_bobbin_m": 85.0,
                "thread_colors": [
                    {"needle": 1, "code": "Same", "name": "Same Match Base", "length_m": 240.0},
                    {"needle": 2, "code": "G-102", "name": "Gold Tilla", "length_m": 120.0},
                    {"needle": 3, "code": "C-305", "name": "Resham Maroon", "length_m": 85.0}
                ]
            },
            "demo_neck": {
                "design_name": "NECK PATTI (14H Alternate)",
                "file_name": "Neck_Patti.pdf",
                "stitches": 22000,
                "repeat": 1.0,
                "mode": "1_rep_half",
                "heads": machine_heads // 2,
                "sequins_total": 0,
                "total_bobbin_m": 42.0,
                "thread_colors": [
                    {"needle": 1, "code": "Same", "name": "Same Match Base", "length_m": 110.0},
                    {"needle": 2, "code": "G-102", "name": "Gold Tilla", "length_m": 65.0}
                ]
            },
            "demo_daman": {
                "design_name": "DAMAN BORDER (4 Head Multi-Color)",
                "file_name": "Daman_Border_(4_Head).pdf",
                "stitches": 100000,
                "repeat": 1.0,
                "mode": "head_4",
                "heads": round(machine_heads / base_colors_count),
                "sequins_total": 0,
                "total_bobbin_m": 160.0,
                "thread_colors": [
                    {"needle": 1, "code": "Same", "name": "Same Match Base", "length_m": 310.0},
                    {"needle": 2, "code": "G-102", "name": "Gold Tilla", "length_m": 180.0},
                    {"needle": 4, "code": "C-412", "name": "Rust Orange", "length_m": 140.0}
                ]
            },
            "demo_sleeves": {
                "design_name": "SLEEVES MOTIF (9 Head)",
                "file_name": "Sleeves_Motif_(9_Head).pdf",
                "stitches": 35000,
                "repeat": 1.0,
                "mode": "head_9",
                "heads": round(machine_heads / 3),
                "sequins_total": 0,
                "total_bobbin_m": 60.0,
                "thread_colors": [
                    {"needle": 2, "code": "G-102", "name": "Gold Tilla", "length_m": 95.0},
                    {"needle": 5, "code": "C-501", "name": "Emerald Green", "length_m": 70.0}
                ]
            }
        }
        st.session_state.custom_same_overrides = {}
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

with c_up_clear:
    st.markdown('<div class="clear-btn-wrap">', unsafe_allow_html=True)
    if st.button("🗑️ Clear", use_container_width=True, help="Tamam parts khatam karein"):
        st.session_state.parts = {}
        st.session_state.suit_design_name = ""
        st.session_state.custom_same_overrides = {}
        st.session_state.uploader_key += 1
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# Parse Uploaded Files
if uploaded_files:
    for u in uploaded_files:
        c = u.getvalue()
        fname = u.name
        is_valid, err_msg = validate_uploaded_file(c, fname)
        if not is_valid:
            st.error(f"⚠️ {fname}: {err_msg}")
            continue

        h = hashlib.sha256(c).hexdigest()
        ext = fname.lower().rsplit(".", 1)[-1]
        if not st.session_state.get("suit_design_name"):
            raw_nm = fname.rsplit(".", 1)[0]
            st.session_state.suit_design_name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', raw_nm).strip() or raw_nm.strip()

        if ext == "pdf":
            try:
                parsed_parts = parse_wilcom_pdf(c, fname)
                if isinstance(parsed_parts, dict):
                    parsed_parts = [parsed_parts]
                for idx, part_data in enumerate(parsed_parts):
                    sub_h = f"{h}_{idx}" if len(parsed_parts) > 1 else h
                    if sub_h not in st.session_state.parts:
                        part_data["hash"] = sub_h
                        part_data["file_name"] = fname
                        st.session_state.parts[sub_h] = part_data
            except Exception as e:
                st.error(f"PDF Parsing Error in {fname}: {e}")
        else:
            if h not in st.session_state.parts:
                try:
                    data = parse_image_part(c, fname)
                    data["hash"] = h
                    data["file_name"] = fname
                    st.session_state.parts[h] = data
                except Exception as e:
                    st.error(f"Image Error in {fname}: {e}")

# Empty State
if not st.session_state.parts:
    st.markdown("""
    <div style="background:var(--bg-surface); border:2px dashed var(--border-main); border-radius:12px; padding:32px 20px; text-align:center; color:var(--text-secondary); margin:12px 0; box-shadow:var(--card-shadow);">
        <div style="font-size:2.8rem; margin-bottom:10px;">📁</div>
        <div style="font-weight:800; font-size:1.15rem; color:var(--text-primary); margin-bottom:6px;">Abhi koi Worksheet Upload Nahi Hui</div>
        <div style="font-size:0.88rem; max-width:540px; margin:0 auto; line-height:1.6; margin-bottom:16px;">
            Upar apni Wilcom PDF production worksheet upload karein, ya foran check karne k liye upar <strong>'✨ Sample Suit Load Karein (Demo)'</strong> button dabayein.
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# ═══════════════════════════════════════════════════════════════════════════
# PARTS CUT-SHEET & HEAD SELECTION CONTROLS (PARTS & HEADS SETTING)
# ═══════════════════════════════════════════════════════════════════════════
col_p_title, col_p_name = st.columns([6.6, 3.4])
with col_p_title:
    st.markdown('<div class="panel-title" style="margin-top:0.6rem;">📋 Design Parts, Repeat aur Head Setting</div>', unsafe_allow_html=True)
with col_p_name:
    if "suit_design_name" not in st.session_state or not st.session_state.suit_design_name:
        first_p = next(iter(st.session_state.parts.values()))
        auto_dn = first_p.get("design_name") or first_p.get("file_name", "Design").rsplit(".", 1)[0]
        st.session_state.suit_design_name = re.sub(r'[\(\[\{].*?[\)\]\}]', '', auto_dn).strip() or auto_dn.strip()

    suit_name_input = st.text_input(
        "🏷️ Design Name / Suit #:",
        value=st.session_state.get("suit_design_name", "Design"),
        key="suit_design_name_input",
        help="Download hone wali tamam files ka naam is design name se banega"
    )
    if suit_name_input != st.session_state.get("suit_design_name"):
        st.session_state.suit_design_name = suit_name_input

mode_options = get_part_mode_options(machine_heads, base_colors_count)
mode_keys = list(mode_options.keys())

part_keys = list(st.session_state.parts.keys())
to_delete = None

for p_key in part_keys:
    p = st.session_state.parts[p_key]
    dname = p.get("design_name", "Part")
    st_raw = int(round(p.get("stitches", 0)))
    target_str = f"{dname} {p.get('file_name', '')}"

    # Auto-detect repeat if not manually edited by user
    if not p.get("_manual_repeat"):
        auto_rep = extract_repeat_from_text(target_str)
        if abs(auto_rep - float(p.get("repeat", 1.0))) > 0.001:
            p["repeat"] = auto_rep
            if not p.get("_manual_mode"):
                p["mode"] = None

    # Compute current configuration
    cur_cfg = compute_part_heads_config(
        target_str,
        float(p.get("repeat", 1.0)),
        machine_heads,
        base_colors_count,
        p
    )
    p["mode"] = cur_cfg["mode"]
    p["repeat"] = cur_cfg["repeat"]
    p["heads"] = cur_cfg["heads"]

    # Calculate live values for this part
    p_suit_st = int(round(st_raw * cur_cfg["rate_st_mult"]))
    p_piece_rate = (p_suit_st / 1000.0) * stitch_rate

    p_rep_factor = float(cur_cfg["repeat"])
    c_in_rep = max(1, cur_cfg.get("colors_in_rep", 1))

    # Factory Machine Repeat Calculation:
    # Har color par design p_rep_factor baar chalta hai:
    # 1 Lot me machine repeats = p_rep_factor * (base_colors_count / c_in_rep)
    # Kul Order me machine repeats = (1 Lot repeats) * lots_count
    p_lot_rep = round(p_rep_factor * (base_colors_count / float(c_in_rep)), 1)
    p_repeat = max(1, int(round(p_lot_rep * lots_count))) if p_rep_factor > 0 else 0

    # Calculate thread usage and dimensions for this part
    p_thread_m = float(p.get("total_thread_m") or sum(tc.get("length_m", 0.0) for tc in p.get("thread_colors", [])))
    raw_tu = str(p.get("raw_thread_usage") or "")
    is_ft = ("ft" in raw_tu.lower()) or (p.get("thread_unit") == "ft")
    p_width = float(p.get("width_mm") or 0.0)
    p_height = float(p.get("height_mm") or 0.0)

    # Build clean inline badges without empty lines to prevent markdown code block bug
    b_type = cur_cfg.get("badge_type", "standard")
    b_badge = cur_cfg.get("badge", "")
    b_desc = cur_cfg.get("desc", "")

    hdr_badges = [
        f'<span class="badge-tag {b_type}">{b_badge}</span>',
        f'<strong style="font-size:1.02rem; font-weight:800; color:var(--text-primary);">{dname}</strong>',
        f'<span style="font-family:\'JetBrains Mono\',monospace; color:var(--accent-amber); font-weight:800; font-size:0.88rem;">Wilcom: {st_raw:,} st</span>'
    ]
    if p_width > 0:
        if p_width > DOUBLE_HEAD_WIDTH_THRESHOLD_MM:
            hdr_badges.append(
                f'<span style="background:rgba(239,68,68,0.15); border:1px solid #ef4444; color:#ef4444; padding:2px 8px; border-radius:5px; font-size:0.78rem; font-weight:800; font-family:\'JetBrains Mono\',monospace;">'
                f'📏 Width: {p_width:g}mm ➔ Auto Double Head (&gt;{DOUBLE_HEAD_WIDTH_THRESHOLD_MM:g}mm)</span>'
            )
        else:
            hdr_badges.append(
                f'<span style="font-family:\'JetBrains Mono\',monospace; color:var(--text-secondary); font-weight:700; font-size:0.84rem;">'
                f'• 📏 Width: {p_width:g}mm</span>'
            )
    if p_thread_m > 0:
        hdr_badges.append(f'<span style="font-family:\'JetBrains Mono\',monospace; color:var(--accent-cyan); font-weight:700; font-size:0.84rem;">• 🧵 Usage: {p_thread_m:,.1f}m</span>')
    if is_ft and raw_tu:
        hdr_badges.append(f'<span style="background:rgba(16,185,129,0.15); border:1px solid var(--accent-green); color:var(--accent-green); padding:1px 6px; border-radius:4px; font-size:0.72rem; font-weight:800; font-family:monospace;">{raw_tu} ➔ {p_thread_m:,.1f}m</span>')

    hdr_html = "".join(hdr_badges)
    card_html = (
        f'<div class="part-card">'
        f'<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:6px;">'
        f'<div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">{hdr_html}</div>'
        f'<div style="font-size:0.85rem; font-weight:800; color:var(--text-primary);">{b_desc}</div>'
        f'</div></div>'
    )

    # Render Part Card
    with st.container():
        st.markdown(card_html, unsafe_allow_html=True)

        c_col1, c_col2, c_col3, c_col4 = st.columns([3.8, 2.4, 3.3, 0.5])

        with c_col1:
            col_m_sel, col_m_rep = st.columns([2.5, 1.3])
            with col_m_sel:
                current_mode_idx = mode_keys.index(cur_cfg["mode"]) if cur_cfg["mode"] in mode_keys else 0
                selected_mode_label = st.selectbox(
                    f"Head Setting ({dname})",
                    options=[mode_options[k] for k in mode_keys],
                    index=current_mode_idx,
                    key=f"mode_sel_{p_key}",
                    label_visibility="collapsed"
                )
                chosen_mode_key = next(k for k, v in mode_options.items() if v == selected_mode_label)
                if chosen_mode_key != p.get("mode"):
                    p["mode"] = chosen_mode_key
                    p["_manual_mode"] = True
                    st.rerun()
            with col_m_rep:
                cur_rep_val = float(p.get("repeat", 1.0))
                new_rep_val = st.number_input(
                    "Repeat",
                    min_value=0.1,
                    max_value=100.0,
                    value=cur_rep_val,
                    step=0.5,
                    format="%.1f" if cur_rep_val % 1 != 0 else "%.0f",
                    key=f"rep_val_{p_key}",
                    label_visibility="collapsed",
                    help=f"{dname} k kitnay repeat 1 suit / piece mein hain"
                )
                if abs(new_rep_val - cur_rep_val) > 0.001:
                    p["repeat"] = new_rep_val
                    p["_manual_repeat"] = True
                    st.rerun()

        with c_col2:
            if p.get("mode") == "custom":
                custom_h = st.number_input(
                    "Machine Heads",
                    min_value=1,
                    max_value=120,
                    value=int(p.get("heads", machine_heads)),
                    step=1,
                    key=f"ch_{p_key}"
                )
                if custom_h != int(p.get("heads", machine_heads)):
                    p["heads"] = custom_h
                    st.rerun()
            else:
                rep_lot_label = f"{p_lot_rep:g} R / Lot" if lots_count > 1 else f"{p_repeat} Repeat"
                rep_sub_label = f"(Kul: {p_repeat} R)" if lots_count > 1 else f"({p_rep_factor:g}R × {base_colors_count} Clr)"
                st.markdown(f"""<div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:8px; padding:6px 10px; font-size:0.82rem; font-weight:700;">
<div style="white-space:nowrap;">🧵 Dhaaga Heads: <strong style="color:var(--accent-cyan); font-weight:800;">{cur_cfg['thread_heads']:.1f} Heads</strong></div>
<div style="white-space:nowrap;">⚡ Machine Repeat: <strong style="color:var(--accent-green); font-weight:800;">{rep_lot_label}</strong> <span style="font-size:0.75rem; color:var(--text-secondary); font-weight:800;">{rep_sub_label}</span></div>
</div>""", unsafe_allow_html=True)

        with c_col3:
            col3_html = (
                f'<div style="background:var(--bg-surface-elevated); border:1px solid var(--border-focus); border-radius:8px; padding:6px 12px; display:flex; justify-content:space-between; align-items:center; gap:8px;">'
                f'<div style="min-width:0; flex-shrink:0;">'
                f'<div style="font-size:0.68rem; color:var(--text-secondary); text-transform:uppercase; font-weight:800; letter-spacing:0.02em; white-space:nowrap;">1 Suit Stitches</div>'
                f'<div style="font-family:\'JetBrains Mono\',monospace; font-weight:900; color:var(--accent-amber); font-size:1.02rem; white-space:nowrap;">{p_suit_st:,} st</div>'
                f'</div>'
                f'<div style="text-align:right; min-width:0; flex-shrink:0;">'
                f'<div style="font-size:0.68rem; color:var(--text-secondary); text-transform:uppercase; font-weight:800; letter-spacing:0.02em; white-space:nowrap;">1 Suit ka Rate</div>'
                f'<div style="font-family:\'JetBrains Mono\',monospace; font-weight:900; color:var(--accent-green); font-size:1.15rem; white-space:nowrap;">Rs {p_piece_rate:,.2f}</div>'
                f'</div></div>'
            )
            st.markdown(col3_html, unsafe_allow_html=True)

        with c_col4:
            st.markdown('<div class="del-btn-wrap" style="margin-top:2px;">', unsafe_allow_html=True)
            if st.button("🗑️", key=f"del_{p_key}", help=f"Remove {dname}", use_container_width=True):
                to_delete = p_key
            st.markdown('</div>', unsafe_allow_html=True)

if to_delete and to_delete in st.session_state.parts:
    del st.session_state.parts[to_delete]
    st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# AGGREGATE CALCULATIONS & PRODUCTION PIPELINE
# ═══════════════════════════════════════════════════════════════════════════
total_suit_stitches, total_suit_sequins, total_suit_bobbin_m, colors_dict = aggregate_suit_parts(
    st.session_state.parts,
    include_boring=False,
    default_heads=machine_heads,
    base_colors=base_colors_count
)

for code in colors_dict:
    if code in st.session_state.custom_same_overrides:
        colors_dict[code]["is_same"] = st.session_state.custom_same_overrides[code]

results = calculate_full_production(
    total_suit_stitches=total_suit_stitches,
    total_suit_bobbin_m=total_suit_bobbin_m,
    colors_dict=colors_dict,
    machine_heads=machine_heads,
    base_colors_count=base_colors_count,
    num_pieces=num_pieces,
    lots_count=lots_count,
    cone_capacity_val=cone_capacity_val,
    cone_unit=cone_unit,
    waste_pct=waste_pct,
    stitch_rate=stitch_rate,
    cone_price=DEFAULT_CONE_PRICE,
    machine_rpm=DEFAULT_MACHINE_RPM,
    shift_hours=DEFAULT_SHIFT_HOURS,
    parts=st.session_state.parts
)

cone_rows = results["cone_rows"]
if cone_rows:
    df_cones = pd.DataFrame(cone_rows).sort_values("Kul Cones (🧵)", ascending=False)
else:
    df_cones = pd.DataFrame()

total_order_cones = results["total_order_cones"]
total_common_cones = results["total_common_cones"]
total_same_cones = results["total_same_cones"]
suits_per_base_color = results["suits_per_base_color"]
total_runs = results["total_runs"]
shifts_needed = results["shifts_needed"]
days_needed = results["days_needed"]
piece_rate = results["piece_rate"]
total_order_amount = results["total_order_amount"]


def format_whatsapp_row(r) -> str:
    code = str(r.get("Code", "")).strip()
    desc = str(r.get("Description", "")).strip()
    is_same = r.get("Is_Same", False)

    raw_chk = r.get("Check_Code")
    chk = ""
    if raw_chk is not None and not pd.isna(raw_chk):
        c_str = str(raw_chk).strip()
        if c_str.lower() not in ("none", "nan", "null", ""):
            chk = c_str

    k_cones = 0
    keys = r.index if hasattr(r, "index") else r.keys()
    for col in keys:
        if "Kul Cones" in str(col):
            k_cones = r[col]
            break

    # Clean description from redundant "(Check: ...)" if present
    desc_clean = re.sub(r'\(Check:[^\)]+\)', '', desc).strip()

    if not desc_clean or desc_clean.lower() == code.lower():
        name_str = f"*{code}*"
    elif code.lower() in desc_clean.lower():
        name_str = f"*{desc_clean}*"
    else:
        name_str = f"*{code}* {desc_clean}"

    if chk and f"Check: {chk}" not in name_str:
        name_str += f" (Check: {chk})"

    if is_same:
        m_per = re.search(r'(\d+)\s*Cones', str(r.get("Per Color Cones", "")))
        per_note = f" ({m_per.group(1)}/color)" if m_per else ""
        return f"• {name_str} [Same]: *{k_cones} Cones*{per_note}"
    else:
        return f"• {name_str}: *{k_cones} Cones*"


# ═══════════════════════════════════════════════════════════════════════════
# TABS (DHAAGA LIST, 1 SUIT RATE BREAKDOWN, JOB SLIP)
# ═══════════════════════════════════════════════════════════════════════════
tab_req, tab_cost, tab_slip = st.tabs([
    "🧵 Dhaaga Order List (Cones Requisition)",
    "💰 1 Suit Rate & Billing Breakdown",
    "🖨️ Factory Job Slip"
])

# ───────────────────────────────────────────────────────────────────────────
# TAB 1: DHAAGA REQUISITION
# ───────────────────────────────────────────────────────────────────────────
with tab_req:
    st.markdown(f"""
    <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:8px; padding:8px 12px; margin-bottom:10px; font-size:0.8rem; color:var(--text-secondary); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
        <span><strong>Order:</strong> {num_pieces} Suits ({lots_count:g} Lots) | <strong>Machine:</strong> {machine_heads} Heads | <strong>Base Colors:</strong> {base_colors_count} ({suits_per_base_color} suits / color)</span>
        <span><strong>1 Cone Size:</strong> {cone_capacity_val:,.0f} {cone_unit} | <strong>Wastage:</strong> {waste_pct:.0f}%</span>
    </div>
    """, unsafe_allow_html=True)

    if not df_cones.empty:
        table_html = """<div class="table-container">
        <table class="modern-table">
        <thead>
        <tr>
        <th style="width:40px;">Sooi # (N#)</th>
        <th>Dhaaga Code</th>
        <th>Shade Name</th>
        <th>Qisam (Category)</th>
        <th>1 Suit (Meters)</th>
        <th>1 Cone / Suit</th>
        <th>Har Color ki Cones</th>
        <th style="color:var(--accent-amber);">Kul Cones (🧵)</th>
        <th>Formula / Detail</th>
        </tr>
        </thead>
        <tbody>"""

        for _, r in df_cones.iterrows():
            is_same = r.get("Is_Same", False)
            badge_html = f'<span class="badge-tag same">Matching (Same)</span>' if is_same else f'<span class="badge-tag standard">Common</span>'
            color_accent = "var(--accent-purple)" if is_same else "var(--accent-cyan)"

            chk_raw = r.get("Check_Code")
            chk_valid = (chk_raw is not None and not pd.isna(chk_raw) and str(chk_raw).strip().lower() not in ("none", "nan", "null", ""))
            chk_badge = f' <span style="background:rgba(245,158,11,0.18); color:#f59e0b; border:1px solid rgba(245,158,11,0.45); font-size:0.72rem; padding:2px 7px; border-radius:4px; font-weight:800; margin-left:6px;" title="1 Head Sample / Check Shirt">Check: {chk_raw}</span>' if chk_valid else ""

            table_html += f"""<tr>
            <td style="font-family:'JetBrains Mono',monospace; color:var(--text-muted); font-weight:700;">N#{r['Needle']}</td>
            <td style="font-weight:700; color:{color_accent}; font-family:'JetBrains Mono',monospace;">{r['Code']}{chk_badge}</td>
            <td><strong>{r['Description']}</strong></td>
            <td>{badge_html}</td>
            <td style="font-family:'JetBrains Mono',monospace;">{r['1 Suit (m)']} m</td>
            <td style="font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">{r['Cones / Suit']:.4f}</td>
            <td style="font-weight:600;">{r['Per Color Cones']}</td>
            <td style="font-weight:900; color:var(--accent-amber); font-family:'JetBrains Mono',monospace; font-size:0.95rem;">{r['Kul Cones (🧵)']} 🧵</td>
            <td style="color:var(--text-secondary); font-size:0.75rem;">{r['Formula / Note']}</td>
            </tr>"""

        table_html += """</tbody></table></div>"""
        st.markdown(table_html, unsafe_allow_html=True)

        raw_design_name = st.session_state.get("suit_design_name", "").strip() or "Design"
        safe_design_prefix = re.sub(r'[\\/*?:"<>|]', '_', raw_design_name).strip()
        safe_design_prefix = re.sub(r'\s+', '_', safe_design_prefix).strip('_')
        if not safe_design_prefix:
            safe_design_prefix = "Design"

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            dhaaga_csv_filename = f"{safe_design_prefix}_Dhaaga_{num_pieces}_suits.csv"
            st.download_button(
                f"📥 Dhaaga List Download Karein ({safe_design_prefix}.csv)",
                df_cones.to_csv(index=False).encode("utf-8-sig"),
                dhaaga_csv_filename,
                "text/csv",
                use_container_width=True
            )
        with col_d2:
            store_summary_text = f"🧵 *DHAAGA ORDER — {raw_design_name}*\n"
            store_summary_text += f"📦 Order: *{num_pieces} Suits* ({lots_count:g} Lots) | *{machine_heads} Heads* | *{base_colors_count} Shades*\n"
            store_summary_text += f"⚡ Stitches: *{total_suit_stitches:,}* | Rate: *Rs {piece_rate:,.2f}*\n"
            store_summary_text += "────────────────────────\n"
            for _, r in df_cones.iterrows():
                store_summary_text += f"{format_whatsapp_row(r)}\n"
            store_summary_text += "────────────────────────\n"
            store_summary_text += f"🧵 *Kul Cones:* {total_order_cones} Cones\n"
            store_summary_text += f"🔄 *Repeat:* {total_runs} Repeat"

            dhaaga_txt_filename = f"{safe_design_prefix}_WhatsApp_Dhaaga_{num_pieces}_suits.txt"
            st.download_button(
                f"📋 WhatsApp Msg Copy Karein ({safe_design_prefix}.txt)",
                store_summary_text,
                dhaaga_txt_filename,
                "text/plain",
                use_container_width=True
            )
    else:
        st.info("💡 Abhi koi dhaaga list mojood nahi hai.")

# ───────────────────────────────────────────────────────────────────────────
# TAB 2: 1 SUIT RATE & ORDER BILLING
# ───────────────────────────────────────────────────────────────────────────
with tab_cost:
    col_fc1, col_fc2 = st.columns([1.2, 0.8])

    with col_fc1:
        st.markdown(f"""<div style="background:var(--bg-surface); border:1px solid var(--border-main); border-radius:10px; padding:14px; box-shadow:var(--card-shadow); margin-bottom:12px;">
<div style="font-size:0.85rem; font-weight:800; text-transform:uppercase; color:var(--accent-amber); margin-bottom:8px;">💵 1 Suit ka Rate Formula aur Parts Breakdown</div>
<div style="background:var(--bg-surface-elevated); border:1.5px solid var(--accent-green); border-radius:8px; padding:12px 16px; margin-bottom:12px;">
<div style="font-size:0.75rem; color:var(--text-secondary); font-weight:800; text-transform:uppercase;">Majmooi Formula: (Kul Stitches × Stitch Rate) ÷ 1,000</div>
<div style="font-size:1.05rem; font-family:'JetBrains Mono',monospace; color:var(--text-primary); margin-top:4px;">(<strong>{total_suit_stitches:,}</strong> stitches × Rs <strong>{stitch_rate:.2f}</strong>) ÷ 1,000</div>
<div style="font-size:1.8rem; font-weight:900; color:var(--accent-green); font-family:'JetBrains Mono',monospace; margin-top:6px;">= Rs {piece_rate:,.2f} <span style="font-size:0.9rem; font-weight:700; color:var(--text-secondary);">/ Suit</span></div>
</div>
<div style="font-size:0.78rem; font-weight:800; color:var(--text-secondary); text-transform:uppercase; margin-bottom:6px;">Har Design Part ka Alag Alag Rate Breakdown:</div>
</div>""", unsafe_allow_html=True)

        parts_table_html = """<div class="table-container">
<table class="modern-table">
<thead>
<tr>
<th>Design Part</th>
<th>Setting</th>
<th style="text-align:right;">Wilcom Stitches (1R)</th>
<th style="text-align:center;">Repeat</th>
<th style="text-align:right;">1 Suit Stitches</th>
<th style="text-align:right; color:var(--accent-green);">1 Suit ka Rate</th>
</tr>
</thead>
<tbody>"""

        part_runs = results.get("part_runs_details", {})
        for p_key, p in st.session_state.parts.items():
            dname = p.get('design_name', 'Part')
            st_raw = int(round(p.get('stitches', 0)))
            p_det = part_runs.get(p_key, {})
            p_suit_st = p_det.get("suit_stitches", st_raw)
            p_rate = p_det.get("rate_per_piece", 0.0)
            badge_text = p_det.get("badge", "")
            p_rep = float(p.get("repeat", 1.0))
            p_rep_display = f"{p_rep:g} R"

            parts_table_html += f"""<tr>
<td><strong>{dname}</strong></td>
<td><span class="badge-tag standard">{badge_text}</span></td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">{st_raw:,}</td>
<td style="text-align:center; font-family:'JetBrains Mono',monospace; font-weight:800; color:var(--accent-amber);">{p_rep_display}</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:700; color:var(--text-primary);">{p_suit_st:,}</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:800; color:var(--accent-green);">Rs {p_rate:,.2f}</td>
</tr>"""

        parts_table_html += f"""<tr style="background:var(--bg-surface-elevated); font-weight:900;">
<td colspan="4" style="color:var(--accent-green);">KUL 1 SUIT KA RATE:</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-primary);">{total_suit_stitches:,} st</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--accent-green); font-size:1.15rem;">Rs {piece_rate:,.2f}</td>
</tr></tbody></table></div>"""

        st.markdown(parts_table_html, unsafe_allow_html=True)

    with col_fc2:
        st.markdown(f"""<div style="background:var(--bg-surface); border:1px solid var(--border-main); border-radius:10px; padding:14px; box-shadow:var(--card-shadow); margin-bottom:12px;">
<div style="font-size:0.85rem; font-weight:800; text-transform:uppercase; color:var(--accent-cyan); margin-bottom:10px;">📦 Poori Lot ka Kul Bill (Order Total Bill)</div>
<div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:8px; padding:12px; margin-bottom:12px;">
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
<span style="font-size:0.75rem; color:var(--text-secondary); font-weight:700;">Kul Production:</span>
<strong style="color:var(--accent-amber); font-weight:800;">{num_pieces} Suits ({lots_count:g} Lots)</strong>
</div>
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
<span style="font-size:0.75rem; color:var(--text-secondary); font-weight:700;">1 Suit ka Rate:</span>
<strong style="color:var(--accent-green); font-family:'JetBrains Mono',monospace; font-weight:900;">Rs {piece_rate:,.2f}</strong>
</div>
<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
<span style="font-size:0.75rem; color:var(--text-secondary); font-weight:700;">Grand Stitches:</span>
<strong style="font-family:'JetBrains Mono',monospace; font-weight:800;">{total_suit_stitches * num_pieces:,} st</strong>
</div>
<hr style="border:0; border-top:1px dashed var(--border-main); margin:8px 0;" />
<div style="display:flex; justify-content:space-between; align-items:baseline;">
<span style="font-size:0.85rem; font-weight:800; color:var(--accent-green);">Poori Lot ka Kul Bill:</span>
<strong style="font-size:1.45rem; font-weight:900; color:var(--accent-green); font-family:'JetBrains Mono',monospace;">Rs {total_order_amount:,.0f}</strong>
</div>
<div style="font-size:0.75rem; color:var(--text-secondary); text-align:right; margin-top:2px; font-weight:700;">{num_pieces} Suits × Rs {piece_rate:,.2f}</div>
</div>
</div>""", unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────
# TAB 3: MASTER JOB SLIP
# ───────────────────────────────────────────────────────────────────────────
with tab_slip:
    master_slip_text = f"""============================================================
              EMBROIDERY JOB SLIP & CONES REQUISITION
============================================================
Design Name: {raw_design_name}
Order: {num_pieces} Suits ({lots_count:g} Lots) | Machine: {machine_heads} Heads
Base Colors: {base_colors_count} Colors ({suits_per_base_color} pcs / color) | Total Repeats: {total_runs} Repeat
Total Stitches per Suit: {total_suit_stitches:,} st
Grand Stitches: {total_suit_stitches * num_pieces:,} st
Rate / 1,000 St: Rs {stitch_rate:.2f} | 1 Piece Rate: Rs {piece_rate:,.2f}
Kul Order Bill ({num_pieces} pcs): Rs {total_order_amount:,.0f}
Machine Shifts: {shifts_needed} Shifts (~{days_needed} Din @ 2 shifts/day)
Cone Size: {cone_capacity_val:,.0f} {cone_unit} | Wastage: {waste_pct:.0f}%
============================================================
SUIT KE PARTS (CUT-SHEET & HEADING):
"""
    for h, p in st.session_state.parts.items():
        st_raw = int(round(p.get('stitches', 0)))
        p_det = part_runs.get(h, {})
        p_suit_st = p_det.get("suit_stitches", st_raw)
        p_c = p_det.get("rate_per_piece", 0.0)
        b_txt = p_det.get("badge", "")
        master_slip_text += f"- {p['design_name']:<30} [{b_txt}]: {p_suit_st:,} st -> Rs {p_c:,.2f}\n"

    master_slip_text += f"""------------------------------------------------------------
DHAAGA REQUISITION (STORE / PURCHASE):
"""
    if not df_cones.empty:
        for _, r in df_cones.iterrows():
            clean_line = format_whatsapp_row(r).replace("*", "")
            master_slip_text += f"{clean_line}\n"
    else:
        master_slip_text += "• (Koi dhaaga list mojood nahi hai)\n"

    master_slip_text += f"""============================================================
1 PIECE RATE: Rs {piece_rate:,.2f}  |  KUL ORDER BILL ({num_pieces} pcs): Rs {total_order_amount:,.0f}
KUL CONES: {total_order_cones} Cones
============================================================
Master Signature: _______________   Store Issue: ___________
"""

    st.text_area("Master Slip Text", master_slip_text, height=220)

    raw_design_name = st.session_state.get("suit_design_name", "").strip() or "Design"
    safe_design_prefix = re.sub(r'[\\/*?:"<>|]', '_', raw_design_name).strip()
    safe_design_prefix = re.sub(r'\s+', '_', safe_design_prefix).strip('_')
    if not safe_design_prefix:
        safe_design_prefix = "Design"

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        job_slip_filename = f"{safe_design_prefix}_Job_Slip_{num_pieces}_suits.txt"
        st.download_button(
            f"📥 Job Slip Download Karein ({safe_design_prefix}.txt)",
            master_slip_text,
            job_slip_filename,
            "text/plain",
            use_container_width=True
        )
    with col_s2:
        whatsapp_msg = f"📋 *JOB SLIP — {raw_design_name}*\n"
        whatsapp_msg += f"📦 Order: *{num_pieces} Suits* ({lots_count:g} Lots) | *{machine_heads} Heads* | *{base_colors_count} Shades*\n"
        whatsapp_msg += f"⚡ Stitches: *{total_suit_stitches:,}* | Rate: *Rs {piece_rate:,.2f}*\n"
        whatsapp_msg += f"💰 Kul Bill: *Rs {total_order_amount:,.0f}*\n"
        whatsapp_msg += f"⏱️ Shifts: ~{shifts_needed} Shifts ({days_needed} Din)\n\n"
        whatsapp_msg += "*PARTS:*\n"
        for h, p in st.session_state.parts.items():
            p_det = part_runs.get(h, {})
            b_txt = p_det.get("badge", "")
            whatsapp_msg += f"• *{p['design_name']}* [{b_txt}]: {p_det.get('suit_stitches', 0):,} st -> Rs {p_det.get('rate_per_piece', 0.0):.2f}\n"
        whatsapp_msg += "\n*DHAAGA:*\n"
        if not df_cones.empty:
            for _, r in df_cones.iterrows():
                whatsapp_msg += f"{format_whatsapp_row(r)}\n"
        whatsapp_msg += f"────────────────────────\n"
        whatsapp_msg += f"🧵 *Kul Cones:* {total_order_cones} Cones | 🔄 *Repeat:* {total_runs}"

        wa_slip_filename = f"{safe_design_prefix}_WhatsApp_Slip_{num_pieces}_suits.txt"
        st.download_button(
            f"📲 WhatsApp Format Copy Karein ({safe_design_prefix}.txt)",
            whatsapp_msg,
            wa_slip_filename,
            "text/plain",
            use_container_width=True
        )
