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
import urllib.parse
import pandas as pd
import streamlit as st
import importlib

# Reload core modules so updates in core/ are always fresh without restarting server
import core.config
import core.security
import core.parser
import core.calculator
import core.pdf_report

importlib.reload(core.config)
importlib.reload(core.security)
importlib.reload(core.parser)
importlib.reload(core.calculator)
importlib.reload(core.pdf_report)

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
    DOUBLE_HEAD_WIDTH_THRESHOLD_MM,
    DEFAULT_HEAD_PITCH_MM,
    DEFAULT_FRAME_MARGIN_METERS,
    DEFAULT_BUKRAM_ROLL_METERS,
    DEFAULT_BUKRAM_ROLL_PRICE,
    DEFAULT_BOBBIN_GRAMS_PER_MILLION_STITCHES,
    DEFAULT_REAL_RPM,
    DEFAULT_COLOR_CHANGE_SECONDS,
    DEFAULT_FRAME_CHANGE_MINUTES,
    DEFAULT_BOBBIN_CONE_PRICE,
    DEFAULT_BOBBIN_RATE_PER_METER
)
from core.security import validate_uploaded_file
from core.parser import parse_wilcom_pdf, parse_image_part, extract_repeat_from_text, extract_dual_shade
from core.pdf_report import generate_job_card_pdf
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
persisted_theme = "Dark" if url_theme == "dark" else "Light"

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

if "saved_speed" not in st.session_state:
    st.session_state.saved_speed = _safe_int_param("speed", DEFAULT_REAL_RPM, 200, 1500)

if "suit_design_name" not in st.session_state:
    st.session_state.suit_design_name = ""

if "parts" not in st.session_state:
    st.session_state.parts = {}

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if "custom_same_overrides" not in st.session_state:
    st.session_state.custom_same_overrides = {}

if "app_mode" not in st.session_state:
    st.session_state.app_mode = "quick"

if "bobbin_cone_cap" not in st.session_state:
    st.session_state.bobbin_cone_cap = 10000.0

if "bobbin_color" not in st.session_state:
    st.session_state.bobbin_color = "White (Sufaid)"


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
        --tab-active-bg: rgba(245, 158, 11, 0.12);
        --accent-amber: #f59e0b;
        --accent-slate: #94a3b8;
        --accent-steel: #38bdf8;
        --accent-green: #10b981;
        --card-shadow: 0 4px 14px rgba(0, 0, 0, 0.45);
        --card-hover-shadow: 0 8px 24px rgba(245, 158, 11, 0.18);
        --del-btn-bg: rgba(239, 68, 68, 0.15);
        --del-btn-border: rgba(239, 68, 68, 0.45);
        --del-btn-text: #f87171;
        --del-btn-hover-bg: rgba(239, 68, 68, 0.35);
        --del-btn-hover-border: #ef4444;
        --del-btn-hover-text: #ffffff;
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
        --border-main: #cbd5e1;
        --border-focus: #d97706;
        --border-subtle: #e2e8f0;
        --text-primary: #0f172a;
        --text-secondary: #334155;
        --text-muted: #64748b;
        --label-color: #0f172a;
        --input-bg: #ffffff;
        --input-border: #94a3b8;
        --btn-bg: #ffffff;
        --btn-border: #cbd5e1;
        --btn-text: #0f172a;
        --btn-hover-bg: #f8fafc;
        --btn-hover-border: #d97706;
        --btn-hover-text: #d97706;
        --table-header-bg: #f1f5f9;
        --table-row-hover: #f8fafc;
        --table-cell-border: #e2e8f0;
        --tab-active-bg: #fef3c7;
        --accent-amber: #d97706;
        --accent-slate: #64748b;
        --accent-steel: #0284c7;
        --accent-green: #059669;
        --card-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
        --card-hover-shadow: 0 8px 20px rgba(217, 119, 6, 0.12);
        --del-btn-bg: #fee2e2;
        --del-btn-border: #fca5a5;
        --del-btn-text: #b91c1c;
        --del-btn-hover-bg: #fecaca;
        --del-btn-hover-border: #dc2626;
        --del-btn-hover-text: #991b1b;
                                                    }
    """

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600;700;800&display=swap');

{theme_css_vars}

*, *::before, *::after {{
    -webkit-font-smoothing: antialiased !important;
    -moz-osx-font-smoothing: grayscale !important;
    text-rendering: optimizeLegibility !important;
}}

html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {{
    background-color: var(--bg-main) !important;
    color: var(--text-primary) !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
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
    grid-template-columns: repeat(auto-fit, minmax(175px, 1fr));
    gap: 10px;
    margin-bottom: 14px;
}}
.kpi-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 9px;
    padding: 12px 14px;
    box-shadow: var(--card-shadow);
    transition: all 0.15s ease;
    position: relative;
    overflow: hidden;
    border-top: 3px solid var(--border-main);
}}
.kpi-card:hover {{
    border-color: var(--accent-amber);
    box-shadow: var(--card-hover-shadow);
    transform: translateY(-1px);
}}
.kpi-card.featured {{
    border-top: 3px solid var(--accent-amber);
    background: var(--bg-surface-elevated);
}}
.kpi-label {{
    font-size: 0.72rem;
    font-weight: 800;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
}}
.kpi-value {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.45rem;
    font-weight: 900;
    line-height: 1.15;
    margin-bottom: 3px;
    color: var(--text-primary);
}}
.kpi-subtext {{
    font-size: 0.74rem;
    color: var(--text-secondary);
    font-weight: 600;
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
    border-radius: 9px;
    padding: 12px 14px;
    margin-bottom: 10px;
    box-shadow: var(--card-shadow);
    transition: border-color 0.2s ease;
}}
.part-card:hover {{
    border-color: var(--border-focus);
}}

/* Clean Badges */
.badge-tag {{
    display: inline-block;
    padding: 2px 7px;
    border-radius: 5px;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}}
.badge-tag.standard {{
    background: rgba(148, 163, 184, 0.15);
    border: 1px solid rgba(148, 163, 184, 0.35);
    color: var(--text-primary);
}}
.badge-tag.double {{
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: var(--accent-amber);
}}
.badge-tag.multi {{
    background: rgba(148, 163, 184, 0.15);
    border: 1px solid rgba(148, 163, 184, 0.35);
    color: var(--text-secondary);
}}
.badge-tag.same {{
    background: rgba(245, 158, 11, 0.15);
    border: 1px solid rgba(245, 158, 11, 0.45);
    color: var(--accent-amber);
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

/* Text Area (Job Slip) */
div[data-testid="stTextArea"] textarea {{
    background-color: var(--input-bg) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--input-border) !important;
    border-radius: 8px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.84rem !important;
    line-height: 1.5 !important;
}}
div[data-testid="stTextArea"] textarea:focus {{
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
div[data-testid="stNumberInput"] button:hover svg {{
    fill: var(--accent-amber) !important;
}}

/* Modern Streamlit 1.64 React-Aria & BaseWeb Selectbox */
.stApp div[data-testid="stSelectbox"] [class*="e1fp86qc0"],
.stApp div[data-testid="stSelectbox"] .react-aria-Group,
.stApp div[data-testid="stSelectbox"] [data-baseweb="select"],
.stApp div[data-testid="stSelectbox"] [data-baseweb="select"] > div,
.stApp div[data-testid="stSelectbox"] > div:has(input),
.stApp div[data-testid="stSelectbox"] > div:last-child:not([data-testid="stWidgetLabel"]) {{
    background-color: var(--input-bg) !important;
    border: 1px solid var(--input-border) !important;
    border-radius: 7px !important;
    color: var(--text-primary) !important;
    box-shadow: none !important;
    min-height: 38px !important;
}}

.stApp div[data-testid="stSelectbox"] [class*="e1fp86qc0"]:hover,
.stApp div[data-testid="stSelectbox"] .react-aria-Group:hover,
.stApp div[data-testid="stSelectbox"] [data-baseweb="select"]:hover,
.stApp div[data-testid="stSelectbox"] [data-baseweb="select"] > div:hover {{
    border-color: var(--border-focus) !important;
    background-color: var(--input-bg) !important;
}}

.stApp div[data-testid="stSelectbox"] [class*="e1fp86qc0"][data-focus-within],
.stApp div[data-testid="stSelectbox"] .react-aria-Group:focus-within {{
    border-color: var(--border-focus) !important;
    background-color: var(--input-bg) !important;
    box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.25) !important;
}}

/* Text input inside the selectbox */
.stApp [data-testid="stSelectbox"] input,
.stApp [data-testid="stSelectbox"] input[type="text"],
.stApp [data-testid="stSelectbox"] [class*="e1fp86qc1"],
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] span,
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] div,
.stApp [data-testid="stSelectbox"] [data-baseweb="select"] p,
.stApp [data-baseweb="select"] span,
.stApp [data-baseweb="select"] div,
.stApp [data-baseweb="select"] p {{
    background-color: transparent !important;
    color: var(--text-primary) !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
    opacity: 1 !important;
}}

/* Arrow button and icons */
.stApp [data-testid="stSelectbox"] button,
.stApp [data-testid="stSelectbox"] svg,
.stApp [data-testid="stSelectbox"] [class*="e1fp86qc2"],
.stApp [data-testid="stSelectbox"] [class*="e1fp86qc2"] svg,
.stApp [data-baseweb="select"] svg {{
    fill: var(--text-primary) !important;
    color: var(--text-primary) !important;
    background: transparent !important;
}}

/* Dropdown Popup Menu (Virtual Dropdown) */
div[data-testid="stSelectboxVirtualDropdown"],
div[data-testid="stSelectboxVirtualDropdown"] > div,
div[data-baseweb="popover"],
div[data-baseweb="popover"] > div,
ul[role="listbox"],
div[role="listbox"],
[class*="e1fp86qc4"],
[class*="e1fp86qc5"] {{
    background-color: var(--bg-surface-elevated) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    box-shadow: var(--card-shadow) !important;
}}

/* Option Items in Dropdown */
div[role="option"],
li[role="option"],
[class*="e1fp86qc7"] {{
    background-color: transparent !important;
    color: var(--text-primary) !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    padding: 8px 12px !important;
}}

div[role="option"]:hover,
div[role="option"][data-hovered],
div[role="option"][aria-selected="true"],
li[role="option"]:hover,
li[role="option"][aria-selected="true"],
[class*="e1fp86qc7"]:hover,
[class*="e1fp86qc7"][data-hovered] {{
    background-color: var(--table-row-hover) !important;
    color: var(--accent-amber) !important;
}}

/* Modern Expander (Details & Summary) Styling */
.stApp [data-testid="stExpander"],
.stApp .stExpander,
.stApp details,
.stApp [class*="e1a0jn2t"] {{
    background-color: var(--bg-surface) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 10px !important;
    margin-bottom: 12px !important;
    box-shadow: var(--card-shadow) !important;
    overflow: hidden !important;
}}

.stApp [data-testid="stExpander"] details,
.stApp details[class*="e1a0jn2t2"] {{
    border: none !important;
    background-color: transparent !important;
}}

.stApp [data-testid="stExpander"] summary,
.stApp summary[class*="e1a0jn2t10"],
.stApp [data-testid="stExpander"] summary[aria-expanded] {{
    background-color: var(--bg-surface-elevated) !important;
    border: none !important;
    border-bottom: 1px solid var(--border-subtle) !important;
    padding: 10px 14px !important;
    color: var(--text-primary) !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
    cursor: pointer !important;
    transition: all 0.15s ease !important;
    display: flex !important;
    align-items: center !important;
    gap: 8px !important;
}}

.stApp [data-testid="stExpander"] summary:hover,
.stApp summary[class*="e1a0jn2t10"]:hover {{
    background-color: var(--btn-hover-bg) !important;
}}

.stApp [data-testid="stExpander"] summary *,
.stApp [data-testid="stExpander"] summary p,
.stApp [data-testid="stExpander"] summary span,
.stApp [data-testid="stExpander"] summary div,
.stApp summary[class*="e1a0jn2t10"] *,
.stApp [class*="e1a0jn2t4"] * {{
    color: var(--text-primary) !important;
    font-size: 0.88rem !important;
    font-weight: 700 !important;
}}

.stApp [data-testid="stExpander"] summary:hover *,
.stApp [data-testid="stExpander"] summary:hover p,
.stApp [data-testid="stExpander"] summary:hover span {{
    color: var(--accent-amber) !important;
}}

.stApp [data-testid="stExpander"] summary svg,
.stApp summary[class*="e1a0jn2t10"] svg {{
    fill: var(--text-primary) !important;
    color: var(--text-primary) !important;
}}

.stApp [data-testid="stExpander"] summary:hover svg {{
    fill: var(--accent-amber) !important;
    color: var(--accent-amber) !important;
}}

.stApp [data-testid="stExpander"] [data-testid="stExpanderDetails"],
.stApp div[class*="e1a0jn2t11"] {{
    background-color: var(--bg-surface) !important;
    padding: 14px 16px !important;
    color: var(--text-primary) !important;
}}

/* High-Contrast Crisp Widget Labels - Strictly Borderless */
.stApp [data-testid="stWidgetLabel"],
.stApp [data-testid="stWidgetLabel"] *,
.stApp div[data-testid="stSelectbox"] [data-testid="stWidgetLabel"],
.stApp div[data-testid="stSelectbox"] [data-testid="stWidgetLabel"] *,
.stApp div[data-testid="stNumberInput"] [data-testid="stWidgetLabel"],
.stApp div[data-testid="stNumberInput"] [data-testid="stWidgetLabel"] * {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    outline: none !important;
    min-height: auto !important;
    height: auto !important;
    padding: 0 !important;
}}
.stApp [data-testid="stWidgetLabel"] {{
    margin-bottom: 4px !important;
}}
.stApp [data-testid="stWidgetLabel"] label,
.stApp [data-testid="stWidgetLabel"] label p,
.stApp [data-testid="stWidgetLabel"] label span {{
    color: var(--label-color) !important;
    font-weight: 700 !important;
    font-size: 0.81rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.025em !important;
    line-height: 1.3 !important;
}}
.stApp [data-testid="stWidgetLabel"] svg,
.stApp [data-testid="stTooltipIcon"] svg {{
    fill: var(--text-muted) !important;
    color: var(--text-muted) !important;
}}
.stApp [data-testid="stTooltipIcon"] {{
    margin-left: 5px !important;
    display: inline-flex !important;
    align-items: center !important;
    vertical-align: middle !important;
}}

/* Standard Button System */
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
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.15) !important;
    transition: all 0.15s ease !important;
}}
.stButton > button:hover,
button[kind="primary"]:hover,
button[kind="secondary"]:hover,
div[data-testid="stDownloadButton"] > button:hover {{
    background-color: var(--btn-hover-bg) !important;
    color: var(--btn-hover-text) !important;
    border-color: var(--border-focus) !important;
    box-shadow: var(--card-hover-shadow) !important;
}}

/* Specialized Toolbar Buttons */
/* (Demo button styles removed) */
.clear-btn-wrap .stButton > button {{
    background: var(--del-btn-bg) !important;
    border: 1.5px solid var(--del-btn-border) !important;
    color: var(--del-btn-text) !important;
    font-weight: 700 !important;
}}
.clear-btn-wrap .stButton > button:hover {{
    background: var(--del-btn-hover-bg) !important;
    border-color: var(--del-btn-hover-border) !important;
    color: var(--del-btn-hover-text) !important;
}}
.del-btn-wrap .stButton > button {{
    background: var(--del-btn-bg) !important;
    border: 1.5px solid var(--del-btn-border) !important;
    color: var(--del-btn-text) !important;
    border-radius: 8px !important;
    font-size: 1.15rem !important;
    padding: 6px !important;
}}
.del-btn-wrap .stButton > button:hover {{
    background: var(--del-btn-hover-bg) !important;
    border-color: var(--del-btn-hover-border) !important;
    color: var(--del-btn-hover-text) !important;
}}

/* File Uploader Dropzone (Light & Dark Mode) */
.stApp div[data-testid="stFileUploader"] {{
    background: transparent !important;
}}
.stApp div[data-testid="stFileUploader"] section {{
    background-color: var(--bg-surface) !important;
    border: 1px dashed var(--border-main) !important;
    border-radius: 8px !important;
    padding: 8px 12px !important;
}}
.stApp div[data-testid="stFileUploader"] section:hover {{
    border-color: var(--border-focus) !important;
}}
.stApp div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"],
.stApp div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] *,
.stApp div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] span,
.stApp div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] small,
.stApp div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"] div,
.stApp div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] *,
.stApp div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] span,
.stApp div[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"] small {{
    color: var(--text-secondary) !important;
    font-size: 0.8rem !important;
    font-weight: 600 !important;
    opacity: 1 !important;
}}

/* Uploaded Files Chips & Items (Streamlit 1.64+) */
.stApp [data-testid="stFileChips"],
.stApp div[data-testid="stFileChips"] {{
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
    margin-top: 8px !important;
}}

.stApp .stFileChip,
.stApp [data-testid="stFileChip"],
.stApp div[class*="e1dmul8p3"],
.stApp [data-testid="stFileUploaderFile"],
.stApp div[data-testid="stFileUploaderFile"] {{
    background-color: var(--bg-surface-elevated) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 8px !important;
    padding: 6px 12px !important;
    box-shadow: var(--card-shadow) !important;
    display: inline-flex !important;
    align-items: center !important;
    gap: 6px !important;
    color: var(--text-primary) !important;
}}

.stApp .stFileChip:hover,
.stApp [data-testid="stFileChip"]:hover,
.stApp div[class*="e1dmul8p3"]:hover,
.stApp div[data-testid="stFileUploaderFile"]:hover {{
    border-color: var(--border-focus) !important;
}}

.stApp [data-testid="stFileUploaderFile"] div,
.stApp [data-testid="stFileUploaderFileData"],
.stApp [data-testid="stFileUploaderFile"] span,
.stApp [data-testid="stFileUploaderFile"] small,
.stApp [data-testid="stFileUploaderFile"] p {{
    background-color: transparent !important;
}}

.stApp .stFileChip *,
.stApp [data-testid="stFileChip"] *,
.stApp div[class*="e1dmul8p3"] *,
.stApp [data-testid="stFileChipName"],
.stApp [data-testid="stFileUploaderFileName"],
.stApp [data-testid="stFileUploaderFile"] * {{
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    font-size: 0.82rem !important;
}}

.stApp .stFileChip svg,
.stApp [data-testid="stFileChip"] svg,
.stApp div[class*="e1dmul8p3"] svg,
.stApp div[data-testid="stFileUploaderFile"] svg {{
    fill: var(--text-primary) !important;
    color: var(--text-primary) !important;
}}

.stApp [data-testid="stFileChipDeleteBtn"],
.stApp [data-testid="stFileChipDeleteBtn"] button,
.stApp div[data-testid="stFileUploaderFile"] button {{
    background: transparent !important;
    color: var(--text-secondary) !important;
    border: none !important;
    padding: 2px !important;
    cursor: pointer !important;
}}

.stApp [data-testid="stFileChipDeleteBtn"]:hover,
.stApp [data-testid="stFileChipDeleteBtn"] button:hover,
.stApp div[data-testid="stFileUploaderFile"] button:hover {{
    color: #ef4444 !important;
}}

.stApp [data-testid="stFileChipDeleteBtn"]:hover svg,
.stApp div[data-testid="stFileUploaderFile"] button:hover svg {{
    fill: #ef4444 !important;
    color: #ef4444 !important;
}}

/* Radio Buttons & Checkboxes (ORDER UNIT: Lots, Suits) */
.stApp [data-testid="stRadio"],
.stApp [data-testid="stRadio"] [role="radiogroup"],
.stApp [data-testid="stRadio"] label,
.stApp [data-testid="stRadio"] label *,
.stApp [data-testid="stRadio"] span,
.stApp [data-testid="stRadio"] p,
.stApp [data-testid="stRadio"] div,
.stApp [data-testid="stRadio"] [class*="e1mpz0hj"],
.stApp [data-testid="stRadio"] [class*="e1mpz0hj"] *,
.stApp [data-testid="stRadio"] [data-testid="stMarkdownContainer"] p,
.stApp [data-testid="stRadio"] [data-testid="stMarkdownContainer"] span,
.stApp [data-testid="stCheckbox"] label,
.stApp [data-testid="stCheckbox"] label * {{
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    font-size: 0.86rem !important;
}}

/* Tab Styling (Streamlit 1.64+ Modern React-Aria Tabs Support) */
.stApp [data-testid="stTabs"] [role="tablist"],
.stApp .stTabs [role="tablist"] {{
    gap: 8px !important;
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 12px !important;
    padding: 6px 8px !important;
    margin-bottom: 14px !important;
    display: flex !important;
    align-items: center !important;
    overflow-x: auto !important;
    white-space: nowrap !important;
    scrollbar-width: thin !important;
}}

/* All Inactive Tabs Base */
.stApp [data-testid="stTabs"] [role="tab"],
.stApp [data-testid="stTabs"] button[role="tab"],
.stApp [data-testid="stTabs"] div[role="tab"],
.stApp [data-testid="stTabs"] [data-testid="stTab"],
.stApp [data-testid="stTab"],
.stApp [data-baseweb="tab"] {{
    background-color: var(--bg-surface-elevated) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    margin: 0 !important;
    height: auto !important;
    min-height: 38px !important;
    transition: all 0.2s ease !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    font-size: 0.88rem !important;
    opacity: 1 !important;
}}

/* Unselected Inactive Tab Text (Force high-contrast text in Light & Dark Mode) */
.stApp [data-testid="stTabs"] [role="tab"] *,
.stApp [data-testid="stTabs"] [data-testid="stTab"] *,
.stApp [data-testid="stTab"] *,
.stApp [data-testid="stTab"] p,
.stApp [data-testid="stTab"] span,
.stApp [data-testid="stTab"] div,
.stApp [data-testid="stTab"] [data-testid="stMarkdownContainer"] p {{
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    font-size: 0.88rem !important;
    letter-spacing: -0.01em !important;
    opacity: 1 !important;
}}

/* Inactive Tab Hover */
.stApp [data-testid="stTabs"] [role="tab"]:hover,
.stApp [data-testid="stTabs"] [data-testid="stTab"]:hover,
.stApp [data-testid="stTab"]:hover {{
    background-color: var(--btn-hover-bg) !important;
    border-color: var(--border-focus) !important;
}}
.stApp [data-testid="stTabs"] [role="tab"]:hover *,
.stApp [data-testid="stTabs"] [data-testid="stTab"]:hover *,
.stApp [data-testid="stTab"]:hover * {{
    color: var(--accent-amber) !important;
}}

/* Active Selected Tab */
.stApp [data-testid="stTabs"] [role="tab"][aria-selected="true"],
.stApp [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"],
.stApp [data-testid="stTab"][aria-selected="true"],
.stApp [data-testid="stTabs"] [role="tab"][data-selected],
.stApp [data-testid="stTabs"] [data-testid="stTab"][data-selected],
.stApp [data-testid="stTab"][data-selected] {{
    background: var(--tab-active-bg) !important;
    border: 2px solid var(--accent-amber) !important;
    box-shadow: 0 4px 14px rgba(245, 158, 11, 0.25) !important;
}}
.stApp [data-testid="stTabs"] [role="tab"][aria-selected="true"] *,
.stApp [data-testid="stTabs"] [data-testid="stTab"][aria-selected="true"] *,
.stApp [data-testid="stTab"][aria-selected="true"] *,
.stApp [data-testid="stTabs"] [role="tab"][data-selected] *,
.stApp [data-testid="stTabs"] [data-testid="stTab"][data-selected] *,
.stApp [data-testid="stTab"][data-selected] * {{
    color: var(--accent-amber) !important;
    font-weight: 800 !important;
}}

/* Remove default Streamlit red underline and highlight line */
.stApp [data-testid="stTabs"] [data-testid="stTabHighlight"],
.stApp [data-testid="stTab"] [data-testid="stTabHighlight"],
.stApp [data-testid="stTabs"] .react-aria-SelectionIndicator,
.stApp [data-testid="stTab"] .react-aria-SelectionIndicator,
.stApp [data-baseweb="tab-highlight"],
.stApp [data-baseweb="tab-border"],
.stApp [data-testid="stTabs"] div[aria-hidden="true"] hr,
.stApp [data-testid="stTabs"] hr {{
    display: none !important;
    height: 0 !important;
    width: 0 !important;
    background-color: transparent !important;
    border: none !important;
}}

/* Quick Mode Pill */
.mode-pill {{
    background: var(--bg-surface-elevated);
    border: 1px solid var(--accent-amber);
    color: var(--accent-amber);
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.76rem;
    font-weight: 800;
    display: inline-flex;
    align-items: center;
    gap: 6px;
}}

</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# TOP HEADER & THEME TOGGLE
# ═══════════════════════════════════════════════════════════════════════════
col_hdr_main, col_hdr_theme = st.columns([7.8, 2.2])

with col_hdr_main:
    st.markdown("""
    <div class="brand-header">
        <div class="brand-title-box">
            <span class="brand-logo-icon">🧵</span>
            <div>
                <div class="brand-main-text">Threadworks • Factory Embroidery ERP</div>
                <div class="brand-sub-text">Separate Systems: Dhaaga (Cones) Calculation & Stitch Rate (per 1,000 stitches)</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_hdr_theme:
    st.markdown('<div class="theme-toggle-wrap" style="padding-top:6px;">', unsafe_allow_html=True)
    theme_icon = "☀️ Light" if is_dark else "🌙 Dark"
    theme_tooltip = "Light Mode" if is_dark else "Dark Mode"
    if st.button(theme_icon, key="theme_toggle_btn", use_container_width=True, help=theme_tooltip):
        new_theme = "Light" if is_dark else "Dark"
        st.session_state.theme_mode = new_theme
        st.query_params["theme"] = new_theme.lower()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# 1. FILE UPLOAD HERO SECTION (TOP PRIORITY ON MOBILE)
# ═══════════════════════════════════════════════════════════════════════════
c_up_box, c_up_reset = st.columns([8.2, 1.8])

with c_up_box:
    uploaded_files = st.file_uploader(
        "Upload Wilcom PDF / Design Images:",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"file_uploader_{st.session_state.uploader_key}",
        label_visibility="collapsed"
    )

with c_up_reset:
    if st.button("🗑️ Reset", key="clear_uploaded_btn", use_container_width=True, help="Tamam files aur calculations clear karein"):
        st.session_state.parts = {}
        st.session_state.suit_design_name = ""
        st.session_state.custom_same_overrides = {}
        st.session_state.uploader_key += 1
        st.rerun()

# Quick Mobile Helper Guide
st.markdown("""
<div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-left:3.5px solid var(--accent-amber); border-radius:8px; padding:8px 12px; margin-bottom:12px; font-size:0.78rem; color:var(--text-secondary); line-height:1.45;">
    📄 <strong>Upload Tip:</strong> Wilcom Production Sheet (PDF) ya mobile photo/scan yahan <strong>Browse files</strong> ya drag-and-drop karke select karein. Dhaaga aur Costing calculation foran load ho jaye gi.
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# 2. MACHINE & ORDER SETTINGS (COMPACT 4 CONTROLS + ADVANCE DRAWER)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown('<div class="panel-title" style="margin-bottom:6px;">⚙️ Order & Machine Settings</div>', unsafe_allow_html=True)
sp1, sp2, sp3, sp4 = st.columns([1.5, 1.5, 2.3, 1.7], gap="medium")

with sp1:
    machine_heads = st.number_input(
        "Machine Heads",
        min_value=1,
        max_value=120,
        value=int(st.session_state.saved_heads),
        step=1
    )
    if machine_heads != st.session_state.saved_heads:
        st.session_state.saved_heads = machine_heads
        st.query_params["heads"] = str(machine_heads)
        st.rerun()

with sp2:
    base_colors_count = st.number_input(
        "Base Shades",
        min_value=1,
        max_value=30,
        value=int(st.session_state.saved_shades),
        step=1
    )
    if base_colors_count != st.session_state.saved_shades:
        st.session_state.saved_shades = base_colors_count
        st.query_params["shades"] = str(base_colors_count)

pieces_per_lot = machine_heads * base_colors_count

with sp3:
    col_q_mode, col_q_val = st.columns([1.0, 1.4])
    with col_q_mode:
        lots_mode = st.radio("Order Unit", ["Lots", "Suits"], index=0, horizontal=True)
    with col_q_val:
        if lots_mode == "Lots":
            lots_count = st.number_input(
                "Kul Lots (LOTS)",
                min_value=0.5,
                max_value=50.0,
                value=float(st.session_state.saved_lots),
                step=0.5,
                help=f"1 Lot = {pieces_per_lot} Suits ({base_colors_count} Shades × {machine_heads}H)"
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

with sp4:
    stitch_rate = st.number_input(
        "Stitch Rate (/1k)",
        min_value=0.05,
        max_value=10.0,
        value=float(st.session_state.saved_rate),
        step=0.05,
        format="%.2f"
    )
    if stitch_rate != st.session_state.saved_rate:
        st.session_state.saved_rate = stitch_rate
        st.query_params["rate"] = f"{stitch_rate:.2f}"

# Collapsed Quick Mode Advance Options (Cone Size, Wastage, Speed, Bobbin)
with st.expander("⚙️ Advance Settings (Cone Size, Wastage %, Speed SPM, Bobbin Khicha)", expanded=False):
    # Row 1: Thread & Cone Settings
    r1_c1, r1_c2, r1_c3 = st.columns([1.2, 1.5, 1.3], gap="medium")
    with r1_c1:
        cone_unit = st.selectbox("Cone Unit", ["Meters", "Yards"], index=0)
    with r1_c2:
        default_cap = DEFAULT_CONE_CAPACITY_METERS if "Meters" in cone_unit else DEFAULT_CONE_CAPACITY_YARDS
        cone_capacity_val = st.number_input("Cone Size", min_value=100.0, max_value=50000.0, value=float(default_cap), step=100.0)
    with r1_c3:
        waste_pct = st.number_input("Wastage %", min_value=0.0, max_value=30.0, value=float(st.session_state.saved_waste), step=1.0, format="%.1f")
        if waste_pct != st.session_state.saved_waste:
            st.session_state.saved_waste = waste_pct
            st.query_params["waste"] = f"{waste_pct:.1f}"

    st.markdown('<div style="height: 4px;"></div>', unsafe_allow_html=True)

    # Row 2: Machine Floor Speed & Bobbin Thread
    r2_c1, r2_c2, r2_c3 = st.columns([1.2, 1.5, 1.3], gap="medium")
    with r2_c1:
        machine_spm = st.number_input("Speed (SPM)", min_value=200, max_value=1500, value=int(st.session_state.saved_speed), step=20)
        if machine_spm != st.session_state.saved_speed:
            st.session_state.saved_speed = machine_spm
            st.query_params["speed"] = str(machine_spm)
    with r2_c2:
        bobbin_cone_capacity = st.number_input("Bobbin Cone (m)", min_value=1000.0, max_value=50000.0, value=float(st.session_state.bobbin_cone_cap), step=1000.0)
        st.session_state.bobbin_cone_cap = bobbin_cone_capacity
    with r2_c3:
        bobbin_color = st.selectbox("Bobbin Color", ["White (Sufaid)", "Black (Kala)", "White + Black"], index=0)
        st.session_state.bobbin_color = bobbin_color

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

        # Feature 1: Auto-detect machine heads from file name if present
        h_match = re.search(r'(20|24|28|30|32|36|40|44|48|56)\s*(?:head|heads|h)', fname, re.I)
        if h_match and not st.session_state.get("_user_set_heads"):
            auto_heads_val = int(h_match.group(1))
            if auto_heads_val != st.session_state.saved_heads:
                st.session_state.saved_heads = auto_heads_val
                st.query_params["heads"] = str(auto_heads_val)

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

# Empty State (When no files uploaded)
if not st.session_state.parts:
    st.markdown("""
    <div style="background:var(--bg-surface); border:2px dashed var(--border-main); border-radius:12px; padding:32px 20px; text-align:center; color:var(--text-secondary); margin:12px 0; box-shadow:var(--card-shadow);">
        <div style="font-size:2.8rem; margin-bottom:10px;">📁</div>
        <div style="font-weight:800; font-size:1.15rem; color:var(--text-primary); margin-bottom:6px;">
            Abhi Koi Wilcom Worksheet Upload Nahi Hui
        </div>
        <div style="font-size:0.86rem; max-width:520px; margin:0 auto; line-height:1.6; color:var(--text-secondary);">
            Upar <strong>'Browse files'</strong> dabayein aur WhatsApp se aayi hui Wilcom PDF ya photo select karein.<br/>
            <span style="font-size:0.78rem; color:var(--text-muted);">(Android mobile par WhatsApp files <strong>Recent</strong> ya <strong>Documents ➔ WhatsApp</strong> mein hoti hain)</span>
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
    machine_rpm=machine_spm,
    shift_hours=DEFAULT_SHIFT_HOURS,
    parts=st.session_state.parts,
    bobbin_cone_capacity_val=float(st.session_state.get("bobbin_cone_cap", 10000.0))
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
part_runs = results.get("part_runs_details", {})

# Bukram / Backing Material
frame_length_m = results.get("frame_length_m", 0.0)
total_bukram_m = results.get("total_bukram_m", 0.0)
bukram_rolls_int = results.get("bukram_rolls_int", 0)
bukram_cost_suit = results.get("bukram_cost_suit", 0.0)
bukram_cost_order = results.get("bukram_cost_order", 0.0)

# Bobbin / Khicha (Exact industrial metric: grams + kg + cones)
bobbin_grams = results.get("bobbin_grams", 0.0)
bobbin_kg = results.get("bobbin_kg", 0.0)
bobbin_cones = results.get("bobbin_cones", 0)
total_order_bobbin_m = results.get("order_bobbin_m", 0.0)
b_clr_label = str(st.session_state.get("bobbin_color", "White (Sufaid)"))
bobbin_cost_suit = results.get("bobbin_cost_suit", 0.0)
bobbin_cost_order = results.get("bobbin_cost_order", 0.0)

# Needle Bar Sequence Map
needle_bar_map = results.get("needle_bar_map", [])

# Real Machine Floor Timing
real_total_hours = results.get("real_total_hours", 0.0)
real_shifts = results.get("real_shifts", shifts_needed)
real_days = results.get("real_days", days_needed)
color_change_loss_mins = results.get("color_change_loss_mins", 0.0)
frame_change_loss_mins = results.get("frame_change_loss_mins", 0.0)

# Costing & Net Profit (Munafa)
dhaaga_cost_suit = results.get("dhaaga_cost_suit", 0.0)
dhaaga_cost_order = results.get("dhaaga_cost_order", 0.0)
total_cost_per_suit = results.get("total_cost_per_suit", 0.0)
total_order_cost = results.get("total_order_cost", 0.0)
net_profit_per_suit = results.get("net_profit_per_suit", 0.0)
total_order_profit = results.get("total_order_profit", 0.0)


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


# KPI Metric Cards Grid (Monochromatic Industrial Palette)
st.markdown(f"""
<div class="kpi-grid">
    <div class="kpi-card featured">
        <div class="kpi-label">🧵 Kul Dhaaga Cones</div>
        <div class="kpi-value">{total_order_cones} Cones</div>
        <div class="kpi-subtext">Common: {total_common_cones} | Same: {total_same_cones}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">💵 1 Suit Rate (PKR)</div>
        <div class="kpi-value">Rs {piece_rate:,.2f}</div>
        <div class="kpi-subtext">Stitch Rate: Rs {stitch_rate:.2f} / 1k st</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">📦 Poori Lot ka Bill</div>
        <div class="kpi-value">Rs {total_order_amount:,.0f}</div>
        <div class="kpi-subtext">{num_pieces} Suits ({lots_count:g} Lots)</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">📜 Bukram / Paper</div>
        <div class="kpi-value">{bukram_rolls_int} Rolls</div>
        <div class="kpi-subtext">{total_bukram_m:,.0f}m (Frame: {frame_length_m:.1f}m)</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">🧵 Bobbin / Khicha</div>
        <div class="kpi-value">{bobbin_cones} Cones</div>
        <div class="kpi-subtext">~{bobbin_kg:.2f} kg ({bobbin_grams:,.0f}g) • {b_clr_label}</div>
    </div>
    <div class="kpi-card">
                <div class="kpi-label">⏱️ Factory Shifts</div>
        <div class="kpi-value">~{real_shifts} Shifts</div>
        <div class="kpi-subtext">~{real_days} Din ({real_total_hours}h @ {machine_spm} SPM)</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════
# TABS ARCHITECTURE (STORE REQUISITION, MACHINE FLOOR & COSTING)
# ═══════════════════════════════════════════════════════════════════════════
tab_store, tab_floor, tab_costing = st.tabs([
    "📦 Store Requisition (Dhaaga & Bukram)",
    "⚙️ Machine Floor & Operator Card",
    "💰 Costing, Munafa & Job Card"
])

# Prepare PDF Data early for downloads
raw_design_name = st.session_state.get("suit_design_name", "").strip() or "Design"
safe_design_prefix = re.sub(r'[\\/*?:"<>|]', '_', raw_design_name).strip()
safe_design_prefix = re.sub(r'\s+', '_', safe_design_prefix).strip('_')
if not safe_design_prefix:
    safe_design_prefix = "Design"

pdf_parts_list = []
for h, p in st.session_state.parts.items():
    st_raw = int(round(p.get('stitches', 0)))
    p_det = part_runs.get(h, {})
    pdf_parts_list.append({
        "name": p.get("design_name", "Part"),
        "setting": p_det.get("badge", ""),
        "wilcom_st": st_raw,
        "repeat": float(p.get("repeat", 1.0)),
        "suit_st": p_det.get("suit_stitches", st_raw),
        "rate": float(p_det.get("rate_per_piece", 0.0))
    })

pdf_cones_list = []
for _, r in df_cones.iterrows():
    pdf_cones_list.append({
        "needle": r.get("Sooi #", r.get("Needle", "")),
        "code": r.get("Code", ""),
        "desc": r.get("Description", ""),
        "type": "Matching (Same)" if r.get("Is_Same") else "Common",
        "suit_m": r.get("1 Suit (m)", 0.0),
        "cones": r.get("Kul Cones (🧵)", 0)
    })

bobbin_dict = {
    "color": b_clr_label,
    "cones": bobbin_cones,
    "meters": total_order_bobbin_m,
    "kg": bobbin_kg
}

bukram_dict = {
    "rolls": bukram_rolls_int,
    "meters": total_bukram_m,
    "frame_len": frame_length_m
}

job_card_pdf_bytes = generate_job_card_pdf(
    design_name=raw_design_name,
    num_pieces=num_pieces,
    lots_count=lots_count,
    machine_heads=machine_heads,
    base_colors_count=base_colors_count,
    suits_per_base_color=suits_per_base_color,
    total_suit_stitches=total_suit_stitches,
    stitch_rate=stitch_rate,
    piece_rate=piece_rate,
    total_order_amount=total_order_amount,
    cone_capacity_val=cone_capacity_val,
    cone_unit=cone_unit,
    waste_pct=waste_pct,
    shifts_needed=real_shifts,
    days_needed=real_days,
    total_runs=total_runs,
    parts_data=pdf_parts_list,
    cones_data=pdf_cones_list,
    total_order_cones=total_order_cones,
    bobbin_data=bobbin_dict,
    bukram_data=bukram_dict
)

# ───────────────────────────────────────────────────────────────────────────
# TAB 1: STORE REQUISITION (DHAAGA, BUKRAM & BOBBIN)
# ───────────────────────────────────────────────────────────────────────────
with tab_store:
    st.markdown(f"""
    <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:8px; padding:10px 14px; margin-bottom:12px; font-size:0.83rem; color:var(--text-secondary); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
        <div>
            <strong style="color:var(--text-primary); font-size:0.88rem;">📦 Store Issue Summary:</strong>
            <span style="margin-left:8px;">🧵 <strong>Dhaaga:</strong> {total_order_cones} Cones</span>
            <span style="margin-left:12px;">🧵 <strong>Bobbin:</strong> {bobbin_cones} Cones (~{bobbin_kg:.2f} kg)</span>
            <span style="margin-left:12px;">📜 <strong>Bukram/Paper:</strong> {bukram_rolls_int} Rolls ({total_bukram_m:,.0f}m)</span>
        </div>
        <div>
            <span>Order: <strong>{num_pieces} Suits</strong> ({lots_count:g} Lots) | Machine: <strong>{machine_heads}H</strong> | <strong>{total_runs} Repeats</strong></span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not df_cones.empty:
        table_html = """<div class="table-container">
        <table class="modern-table">
        <thead>
        <tr>
        <th style="width:50px;">Sooi #</th>
        <th>Dhaaga Code</th>
        <th>Shade Name</th>
        <th>Qisam (Category)</th>
        <th style="text-align:right;">1 Suit (m)</th>
        <th style="text-align:right;">1 Cone / Suit</th>
        <th>Har Color ki Cones</th>
        <th style="color:var(--accent-amber); text-align:right;">Kul Cones (🧵)</th>
        <th>Formula / Detail</th>
        </tr>
        </thead>
        <tbody>"""

        for _, r in df_cones.iterrows():
            is_same = r.get("Is_Same", False)
            badge_html = f'<span class="badge-tag same">Matching (Same)</span>' if is_same else f'<span class="badge-tag standard">Common</span>'

            chk_raw = r.get("Check_Code")
            chk_valid = (chk_raw is not None and not pd.isna(chk_raw) and str(chk_raw).strip().lower() not in ("none", "nan", "null", ""))
            chk_badge = f' <span style="background:rgba(245,158,11,0.18); color:var(--accent-amber); border:1px solid rgba(245,158,11,0.45); font-size:0.72rem; padding:2px 7px; border-radius:4px; font-weight:800; margin-left:6px;" title="Sample / Check Shirt">Check: {chk_raw}</span>' if chk_valid else ""

            table_html += f"""<tr>
            <td style="font-family:'JetBrains Mono',monospace; color:var(--text-muted); font-weight:700;">N#{r['Needle']}</td>
            <td style="font-weight:700; color:var(--text-primary); font-family:'JetBrains Mono',monospace;">{r['Code']}{chk_badge}</td>
            <td><strong>{r['Description']}</strong></td>
            <td>{badge_html}</td>
            <td style="font-family:'JetBrains Mono',monospace; text-align:right;">{r['1 Suit (m)']} m</td>
            <td style="font-family:'JetBrains Mono',monospace; color:var(--text-secondary); text-align:right;">{r['Cones / Suit']:.4f}</td>
            <td style="font-weight:600;">{r['Per Color Cones']}</td>
            <td style="font-weight:900; color:var(--accent-amber); font-family:'JetBrains Mono',monospace; font-size:0.95rem; text-align:right;">{r['Kul Cones (🧵)']} 🧵</td>
            <td style="color:var(--text-secondary); font-size:0.75rem;">{r['Formula / Note']}</td>
            </tr>"""

        table_html += """</tbody></table></div>"""
        st.markdown(table_html, unsafe_allow_html=True)

        # WhatsApp simple dhaaga order text (Sirf Dhaaga & Cones)
        store_summary_text = f"🧵 *DHAAGA ORDER — {raw_design_name}*\n"
        store_summary_text += f"📦 Order: *{num_pieces} Suits* ({lots_count:g} Lots)\n"
        store_summary_text += "────────────────────────\n"
        for _, r in df_cones.iterrows():
            store_summary_text += f"{format_whatsapp_row(r)}\n"
        store_summary_text += "────────────────────────\n"
        store_summary_text += f"🧵 *Kul Dhaaga Cones:* *{total_order_cones} Cones*\n"
        if bobbin_cones > 0:
            store_summary_text += f"🧵 *Bobbin/Khicha ({b_clr_label})*: *{bobbin_cones} Cones* (~{bobbin_kg:.1f} kg)"

        wa_encoded = urllib.parse.quote(store_summary_text)
        wa_direct_url = f"https://api.whatsapp.com/send?text={wa_encoded}"

        col_d1, col_d2, col_d3, col_d4 = st.columns([1.5, 1.3, 1.4, 1.0])
        with col_d1:
            st.markdown(f'<a href="{wa_direct_url}" target="_blank" class="wa-direct-btn">📲 Direct WhatsApp Bhejein</a>', unsafe_allow_html=True)
        with col_d2:
            dhaaga_txt_filename = f"{safe_design_prefix}_WhatsApp_Store_{num_pieces}_suits.txt"
            st.download_button(
                f"📋 Msg Copy Karein ({safe_design_prefix}.txt)",
                store_summary_text,
                dhaaga_txt_filename,
                "text/plain",
                use_container_width=True,
                key="btn_dl_dhaaga_txt_tab1"
            )
        with col_d3:
            st.download_button(
                f"🖨️ Job Card (PDF Print)",
                job_card_pdf_bytes,
                f"{safe_design_prefix}_Job_Card_{num_pieces}_suits.pdf",
                "application/pdf",
                use_container_width=True,
                key="btn_dl_pdf_tab1"
            )
        with col_d4:
            dhaaga_csv_filename = f"{safe_design_prefix}_Dhaaga_{num_pieces}_suits.csv"
            st.download_button(
                f"📥 Excel (CSV)",
                df_cones.to_csv(index=False).encode("utf-8-sig"),
                dhaaga_csv_filename,
                "text/csv",
                use_container_width=True,
                key="btn_dl_csv_tab1"
            )

        with st.expander("👁️ WhatsApp Message Preview (Single-Click Copy)", expanded=False):
            st.code(store_summary_text, language="markdown")
    else:
        st.info("💡 Abhi koi dhaaga list mojood nahi hai.")

# ───────────────────────────────────────────────────────────────────────────
# TAB 2: MACHINE FLOOR & OPERATOR CARD
# ───────────────────────────────────────────────────────────────────────────
with tab_floor:
    # 1. Needle Bar Sequence Map (1 to 15)
    st.markdown(f"""
    <div style="background:var(--bg-surface); border:1px solid var(--border-main); border-radius:9px; padding:12px 14px; margin-bottom:12px;">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <div>
                <div style="font-size:0.86rem; font-weight:800; text-transform:uppercase; color:var(--accent-amber);">🪡 Needle Bar Sequence Map (Sooi 1 se 15 Setup Card)</div>
                <div style="font-size:0.75rem; color:var(--text-secondary); margin-top:2px;">Machine operator k liye reference: Kis sooi par konsa dhaaga, tilla, matching shade ya churi lagegi.</div>
            </div>
            <div style="font-family:'JetBrains Mono',monospace; font-size:0.8rem; font-weight:800; background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:6px; padding:4px 10px;">
                Active Needles: {len(needle_bar_map)}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    needle_table_html = """<div class="table-container">
    <table class="modern-table">
    <thead>
    <tr>
    <th style="width:55px; text-align:center;">Sooi #</th>
    <th>Dhaaga Code</th>
    <th>Shade Description</th>
    <th>Tooling / Qisam</th>
    <th>Check Shirt (Sample)</th>
    <th style="text-align:right;">1 Suit Usage</th>
    <th style="text-align:right;">Kul Cones</th>
    </tr>
    </thead>
    <tbody>"""

    for row in needle_bar_map:
        n_num = row["needle"]
        c_code = row["code"]
        c_name = row["name"]
        c_tool = row["tooling"]
        c_chk = row.get("check_code")
        c_m = row.get("m_1_suit", 0.0)
        c_cones = row.get("cones", 0)

        chk_badge = f'<span style="background:rgba(245,158,11,0.18); color:var(--accent-amber); border:1px solid rgba(245,158,11,0.45); font-size:0.72rem; padding:2px 7px; border-radius:4px; font-weight:800;">Check: {c_chk}</span>' if (c_chk and str(c_chk).strip().lower() not in ("none", "nan", "")) else '<span style="color:var(--text-muted); font-size:0.75rem;">—</span>'

        tool_badge = f'<span class="badge-tag standard">{c_tool}</span>'
        if "tilla" in c_tool.lower():
            tool_badge = f'<span class="badge-tag double">{c_tool}</span>'
        elif "same" in c_tool.lower():
            tool_badge = f'<span class="badge-tag same">{c_tool}</span>'
        elif "boring" in c_tool.lower():
            tool_badge = f'<span class="badge-tag standard" style="border-color:#ef4444; color:#ef4444;">{c_tool}</span>'

        needle_table_html += f"""<tr>
        <td style="text-align:center; font-family:'JetBrains Mono',monospace; font-weight:800; color:var(--accent-amber);">N#{n_num}</td>
        <td style="font-family:'JetBrains Mono',monospace; font-weight:700; color:var(--text-primary);">{c_code}</td>
        <td><strong>{c_name}</strong></td>
        <td>{tool_badge}</td>
        <td>{chk_badge}</td>
        <td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">{c_m:,.1f} m</td>
        <td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:800; color:var(--accent-amber);">{c_cones} Cones</td>
        </tr>"""

    needle_table_html += "</tbody></table></div>"
    st.markdown(needle_table_html, unsafe_allow_html=True)

        # 2. Real Floor Timing & Downtime
    pure_stitch_hours = float(results.get("pure_stitch_hours", ((total_suit_stitches / machine_spm) * total_runs / 60.0) if machine_spm > 0 else 0))
    col_rt1, col_rt2 = st.columns([1.1, 0.9])
    with col_rt1:
        st.markdown(f"""<div style="background:var(--bg-surface); border:1px solid var(--border-main); border-radius:9px; padding:14px; box-shadow:var(--card-shadow); margin-bottom:12px;">
<div style="font-size:0.84rem; font-weight:800; text-transform:uppercase; color:var(--accent-amber); margin-bottom:8px;">⏱️ Real Machine Floor Timing & Downtime</div>
<div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:10px;">
    <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:7px; padding:8px 10px;">
        <div style="font-size:0.72rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">Running Speed</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:1.1rem; font-weight:800; color:var(--text-primary);">{machine_spm} SPM</div>
        <div style="font-size:0.7rem; color:var(--text-secondary);">Real Average Floor Speed (Adjustable)</div>
    </div>
    <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:7px; padding:8px 10px;">
        <div style="font-size:0.72rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">Pure Stitching</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:1.1rem; font-weight:800; color:var(--text-primary);">{pure_stitch_hours:.1f} Hours</div>
        <div style="font-size:0.7rem; color:var(--text-secondary);">Baghair Ruke Running Time</div>
    </div>
    <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:7px; padding:8px 10px;">
        <div style="font-size:0.72rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">Color Change Stop</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:1.1rem; font-weight:800; color:var(--text-primary);">{color_change_loss_mins:.0f} Mins</div>
        <div style="font-size:0.7rem; color:var(--text-secondary);">{len(needle_bar_map)} Colors × 10s × {total_runs}R</div>
    </div>
    <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:7px; padding:8px 10px;">
        <div style="font-size:0.72rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">Frame Takaai / Load</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:1.1rem; font-weight:800; color:var(--text-primary);">{frame_change_loss_mins:.0f} Mins</div>
        <div style="font-size:0.7rem; color:var(--text-secondary);">12 Mins × {total_runs} Repeats</div>
    </div>
</div>
<div style="background:var(--bg-surface-elevated); border-left:3px solid var(--accent-amber); border-radius:6px; padding:8px 12px; font-size:0.8rem; color:var(--text-secondary);">
    💡 <strong>Factory Standard:</strong> Theoretical machine speed (850 RPM) kabhi achieve nahi hoti; {machine_spm} SPM average speed, color change stops aur frame badalne ka waqt milakar asal shift time banta hai. Speed tabdeel karne ke liye upar <strong>Advance Settings</strong> kholein.
</div>
</div>""", unsafe_allow_html=True)

    with col_rt2:
        st.markdown(f"""<div style="background:var(--bg-surface); border:1px solid var(--border-main); border-radius:9px; padding:14px; box-shadow:var(--card-shadow); margin-bottom:12px;">
<div style="font-size:0.84rem; font-weight:800; text-transform:uppercase; color:var(--accent-amber); margin-bottom:8px;">📦 Production Schedule & Shifts</div>
<div style="background:var(--bg-surface-elevated); border:1.5px solid var(--border-focus); border-radius:8px; padding:12px; margin-bottom:10px;">
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <span style="font-size:0.76rem; color:var(--text-secondary); font-weight:700;">Kul Asal Floor Waqt:</span>
        <strong style="font-family:'JetBrains Mono',monospace; font-size:1.15rem; color:var(--text-primary);">{real_total_hours} Hours</strong>
    </div>
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
        <span style="font-size:0.76rem; color:var(--text-secondary); font-weight:700;">12-Hour Factory Shifts:</span>
        <strong style="font-family:'JetBrains Mono',monospace; font-size:1.25rem; color:var(--accent-amber);">{real_shifts} Shifts</strong>
    </div>
    <div style="display:flex; justify-content:space-between; align-items:center;">
        <span style="font-size:0.76rem; color:var(--text-secondary); font-weight:700;">Takhmeena Din (2 Shifts/Day):</span>
        <strong style="font-family:'JetBrains Mono',monospace; font-size:1.15rem; color:var(--text-primary);">~{real_days} Din</strong>
    </div>
</div>
<div style="font-size:0.74rem; color:var(--text-muted); line-height:1.4;">
    Total Repeats: <strong>{total_runs} Repeats</strong> • Total Suits: <strong>{num_pieces} Suits</strong> ({lots_count:g} Lots)
</div>
</div>""", unsafe_allow_html=True)

    # 3. Parts Cut-Sheet
    parts_table_html = """<div class="table-container">
    <table class="modern-table">
    <thead>
    <tr>
    <th>Design Part</th>
    <th>Setting</th>
    <th style="text-align:right;">Wilcom Stitches (1R)</th>
    <th style="text-align:center;">Repeat</th>
    <th style="text-align:right;">1 Suit Stitches</th>
    <th style="text-align:right; color:var(--accent-amber);">1 Suit ka Rate</th>
    </tr>
    </thead>
    <tbody>"""

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
        <td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:800; color:var(--text-primary);">Rs {p_rate:,.2f}</td>
        </tr>"""

    parts_table_html += f"""<tr style="background:var(--bg-surface-elevated); font-weight:900;">
    <td colspan="4" style="color:var(--accent-amber);">KUL 1 SUIT KA RATE:</td>
    <td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-primary);">{total_suit_stitches:,} st</td>
    <td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--accent-amber); font-size:1.15rem;">Rs {piece_rate:,.2f}</td>
    </tr></tbody></table></div>"""

    st.markdown(parts_table_html, unsafe_allow_html=True)

# ───────────────────────────────────────────────────────────────────────────
# TAB 3: COSTING, MUNAFA & PRINTABLE JOB CARD
# ───────────────────────────────────────────────────────────────────────────
with tab_costing:
    col_cost1, col_cost2 = st.columns([1.2, 0.8])
    with col_cost1:
        st.markdown(f"""<div style="background:var(--bg-surface); border:1px solid var(--border-main); border-radius:9px; padding:14px; box-shadow:var(--card-shadow); margin-bottom:12px;">
<div style="font-size:0.86rem; font-weight:800; text-transform:uppercase; color:var(--accent-amber); margin-bottom:10px;">💵 1 Suit Costing vs Saaf Munafa (Net Profit)</div>
<div class="table-container" style="margin-bottom:0;">
<table class="modern-table">
<thead>
<tr>
<th>Item / Madad</th>
<th style="text-align:right;">1 Suit Laagat</th>
<th style="text-align:right;">Poori Lot ({num_pieces} Suits)</th>
</tr>
</thead>
<tbody>
<tr>
<td><strong>💵 Stitching Rate (Wasooli):</strong></td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:800; color:var(--accent-amber);">Rs {piece_rate:,.2f}</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:800; color:var(--accent-amber);">Rs {total_order_amount:,.0f}</td>
</tr>
<tr>
<td>🧵 Dhaaga Kharach ({total_order_cones} Cones @ Rs {DEFAULT_CONE_PRICE:.0f})</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">Rs {dhaaga_cost_suit:.2f}</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">Rs {dhaaga_cost_order:,.0f}</td>
</tr>
<tr>
<td>🧵 Bobbin / Khicha Kharach ({bobbin_cones} Cones @ Rs {DEFAULT_BOBBIN_CONE_PRICE:.0f})</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">Rs {bobbin_cost_suit:.2f}</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">Rs {bobbin_cost_order:,.0f}</td>
</tr>
<tr>
<td>📜 Bukram / Paper Kharach ({bukram_rolls_int} Rolls @ Rs {DEFAULT_BUKRAM_ROLL_PRICE:.0f})</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">Rs {bukram_cost_suit:.2f}</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">Rs {bukram_cost_order:,.0f}</td>
</tr>
<tr style="background:var(--bg-surface-elevated); font-weight:800;">
<td>⚡ KUL DIRECT LAAGAT (Cost):</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:800; color:var(--text-primary);">Rs {total_cost_per_suit:.2f}</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:800; color:var(--text-primary);">Rs {total_order_cost:,.0f}</td>
</tr>
<tr style="background:var(--bg-surface-elevated); font-weight:900; border-top:2px solid var(--accent-amber);">
<td style="color:var(--accent-amber); font-size:0.95rem;">🌟 SAAF MUNAFA (NET PROFIT):</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:900; color:var(--accent-amber); font-size:1.15rem;">Rs {net_profit_per_suit:,.2f}</td>
<td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:900; color:var(--accent-amber); font-size:1.15rem;">Rs {total_order_profit:,.0f}</td>
</tr>
</tbody>
</table>
</div>
</div>""", unsafe_allow_html=True)

    with col_cost2:
        margin_pct = (net_profit_per_suit / max(0.01, piece_rate)) * 100.0 if piece_rate > 0 else 0
        st.markdown(f"""<div style="background:var(--bg-surface); border:1px solid var(--border-main); border-radius:9px; padding:14px; box-shadow:var(--card-shadow); margin-bottom:12px;">
<div style="font-size:0.86rem; font-weight:800; text-transform:uppercase; color:var(--accent-amber); margin-bottom:8px;">💰 Munafa Summary Card</div>
<div style="background:var(--bg-surface-elevated); border:1.5px solid var(--accent-amber); border-radius:8px; padding:14px; text-align:center; margin-bottom:12px;">
    <div style="font-size:0.75rem; color:var(--text-muted); font-weight:800; text-transform:uppercase;">Poori Lot ka Saaf Munafa</div>
    <div style="font-size:2rem; font-weight:900; font-family:'JetBrains Mono',monospace; color:var(--accent-amber); margin:4px 0;">Rs {total_order_profit:,.0f}</div>
    <div style="font-size:0.8rem; font-weight:700; color:var(--text-secondary);">{num_pieces} Suits @ Rs {net_profit_per_suit:,.2f} / Suit</div>
</div>
<div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
    <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:7px; padding:8px 10px;">
        <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">Profit Margin</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:1.15rem; font-weight:800; color:var(--accent-amber);">{margin_pct:.1f}%</div>
    </div>
    <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:7px; padding:8px 10px;">
        <div style="font-size:0.7rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">Order Total Bill</div>
        <div style="font-family:'JetBrains Mono',monospace; font-size:1.15rem; font-weight:800; color:var(--text-primary);">Rs {total_order_amount:,.0f}</div>
    </div>
</div>
</div>""", unsafe_allow_html=True)

    # Master Job Slip Text
    master_slip_text = f"""============================================================
              EMBROIDERY JOB SLIP & FACTORY CARD
============================================================
Design Name: {raw_design_name}
Order: {num_pieces} Suits ({lots_count:g} Lots) | Machine: {machine_heads} Heads
Base Colors: {base_colors_count} Colors ({suits_per_base_color} pcs / color) | Total Repeats: {total_runs} Repeat
Total Stitches per Suit: {total_suit_stitches:,} st | Grand Stitches: {total_suit_stitches * num_pieces:,} st
Rate / 1,000 St: Rs {stitch_rate:.2f} | 1 Piece Rate: Rs {piece_rate:,.2f}
Order Bill: Rs {total_order_amount:,.0f} | Est Net Profit: Rs {total_order_profit:,.0f}
Machine Shifts: ~{real_shifts} Shifts (~{real_days} Din @ 680 SPM)
Cone Size: {cone_capacity_val:,.0f} {cone_unit} | Wastage: {waste_pct:.0f}%
============================================================
SUIT KE PARTS (CUT-SHEET):
"""
    for h, p in st.session_state.parts.items():
        p_det = part_runs.get(h, {})
        p_suit_st = p_det.get("suit_stitches", int(round(p.get('stitches', 0))))
        p_c = p_det.get("rate_per_piece", 0.0)
        b_txt = p_det.get("badge", "")
        master_slip_text += f"- {p['design_name']:<30} [{b_txt}]: {p_suit_st:,} st -> Rs {p_c:,.2f}\n"

    master_slip_text += f"""------------------------------------------------------------
DHAAGA & STORE REQUISITION:
"""
    if not df_cones.empty:
        for _, r in df_cones.iterrows():
            clean_line = format_whatsapp_row(r).replace("*", "")
            master_slip_text += f"{clean_line}\n"
    if bobbin_cones > 0:
        master_slip_text += f"• Bobbin/Khicha ({b_clr_label}): {bobbin_cones} Cones (~{bobbin_kg:.2f} kg / {total_order_bobbin_m:,.0f}m)\n"
    if bukram_rolls_int > 0:
        master_slip_text += f"• Bukram/Paper: {bukram_rolls_int} Rolls (~{total_bukram_m:,.0f}m / Frame: {frame_length_m:.1f}m)\n"

    master_slip_text += f"""============================================================
1 PIECE RATE: Rs {piece_rate:,.2f}  |  ORDER BILL: Rs {total_order_amount:,.0f}
KUL CONES: {total_order_cones} Cones  |  EST NET PROFIT: Rs {total_order_profit:,.0f}
============================================================
Master Signature: _______________   Store Issue: ___________
"""

    st.text_area("Master Slip Text", master_slip_text, height=180)

    whatsapp_msg = f"📋 *JOB SLIP — {raw_design_name}*\n"
    whatsapp_msg += f"📦 Order: *{num_pieces} Suits* ({lots_count:g} Lots) | *{machine_heads} Heads* | *{base_colors_count} Shades*\n"
    whatsapp_msg += f"⚡ Stitches: *{total_suit_stitches:,}*\n"
    
    whatsapp_msg += f"⏱️ Shifts: ~{real_shifts} Shifts ({real_days} Din @ {machine_spm} SPM)\n\n"
    whatsapp_msg += "*PARTS:*\n"
    for h, p in st.session_state.parts.items():
        p_det = part_runs.get(h, {})
        b_txt = p_det.get("badge", "")
        whatsapp_msg += f"• *{p['design_name']}* [{b_txt}]: {p_det.get('suit_stitches', 0):,} st\n"
    whatsapp_msg += "\n*DHAAGA & STORE:*\n"
    if not df_cones.empty:
        for _, r in df_cones.iterrows():
            whatsapp_msg += f"{format_whatsapp_row(r)}\n"
    if bobbin_cones > 0:
        whatsapp_msg += f"• *Bobbin/Khicha ({b_clr_label})*: *{bobbin_cones} Cones* (~{bobbin_kg:.2f} kg)\n"
    if bukram_rolls_int > 0:
        whatsapp_msg += f"• *Bukram/Paper*: *{bukram_rolls_int} Rolls* (~{total_bukram_m:,.0f}m)\n"
    whatsapp_msg += f"────────────────────────\n"
    whatsapp_msg += f"🧵 *Kul Cones:* {total_order_cones} Cones | 🔄 *Repeat:* {total_runs}"

    wa_slip_encoded = urllib.parse.quote(whatsapp_msg)
    wa_slip_url = f"https://api.whatsapp.com/send?text={wa_slip_encoded}"

    col_s1, col_s2, col_s3 = st.columns([1.5, 1.4, 1.3])
    with col_s1:
        st.markdown(f'<a href="{wa_slip_url}" target="_blank" class="wa-direct-btn">📲 Direct WhatsApp Job Slip</a>', unsafe_allow_html=True)
    with col_s2:
        st.download_button(
            f"🖨️ Job Card (PDF Print)",
            job_card_pdf_bytes,
            f"{safe_design_prefix}_Job_Card_{num_pieces}_suits.pdf",
            "application/pdf",
            use_container_width=True,
            key="btn_dl_pdf_tab3"
        )
    with col_s3:
        job_slip_filename = f"{safe_design_prefix}_Job_Slip_{num_pieces}_suits.txt"
        st.download_button(
            f"📥 Master Slip (.txt)",
            master_slip_text,
            job_slip_filename,
            "text/plain",
            use_container_width=True,
            key="btn_dl_slip_txt_tab3"
        )
