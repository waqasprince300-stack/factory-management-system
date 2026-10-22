"""
Threadworks — Production & Cones ERP
Compact, High-Density Factory Dashboard with Dual Light & Dark Theme Support.
Supports:
- Wilcom PDF Worksheet & Design Image parsing
- 30/28 Machine Heads multi-part suit calculation
- Multi-lot calculation (e.g. 3 Lots = 540 suits across 6 base colors)
- Exact same-thread formula matching Pakistani embroidery factory standard
- Dual Theme Toggle: 🌙 Dark Mode / ☀️ Light Mode
- Ultra-Compact, High-Density Industrial ERP Layout
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
import core.demo

importlib.reload(core.config)
importlib.reload(core.security)
importlib.reload(core.parser)
importlib.reload(core.calculator)
importlib.reload(core.demo)

# Modular Core Imports
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
    METERS_TO_YARDS
)
from core.security import validate_uploaded_file
from core.parser import parse_wilcom_pdf, parse_image_part
from core.calculator import (
    aggregate_suit_parts,
    calculate_full_production
)
from core.demo import get_demo_parts

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Threadworks ERP • Factory Calculator",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE & BROWSER SETTINGS PERSISTENCE
# Defaults: Light Theme, 28 Heads, 1.0 Lot, 6 Shades, 0.0% Waste, 0.45 Rate
# ═══════════════════════════════════════════════════════════════════════════
url_theme = st.query_params.get("theme", "").strip().lower()
if url_theme in ["dark", "light"]:
    persisted_theme = "Dark" if url_theme == "dark" else "Light"
else:
    persisted_theme = "Light"  # Default: Light theme

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
            val = float(st.query_params[key])
            if key == "rate" and (abs(val - 1.45) < 0.001 or val > 5.0):
                return default_val
            return max(min_v, min(max_v, val))
    except Exception:
        pass
    return default_val

# Default 28 heads and 1.0 lot as requested
if "saved_heads" not in st.session_state:
    st.session_state.saved_heads = _safe_int_param("heads", 28, 1, 120)

if "saved_lots" not in st.session_state:
    st.session_state.saved_lots = _safe_float_param("lots", 1.0, 0.5, 50.0)

if "saved_shades" not in st.session_state:
    st.session_state.saved_shades = _safe_int_param("shades", 6, 1, 30)

if "saved_waste" not in st.session_state:
    st.session_state.saved_waste = _safe_float_param("waste", 0.0, 0.0, 30.0)

if "saved_rate" not in st.session_state or abs(st.session_state.get("saved_rate", 0) - 1.45) < 0.001:
    st.session_state.saved_rate = _safe_float_param("rate", DEFAULT_STITCH_RATE, 0.05, 5.0)

# Synchronize URL query parameters
if st.query_params.get("theme", "").strip().lower() != st.session_state.theme_mode.lower():
    st.query_params["theme"] = st.session_state.theme_mode.lower()

if "heads" not in st.query_params:
    st.query_params["heads"] = str(st.session_state.saved_heads)

if "lots" not in st.query_params:
    st.query_params["lots"] = f"{st.session_state.saved_lots:g}"

if "parts" not in st.session_state:
    st.session_state.parts = {}

if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if "custom_same_overrides" not in st.session_state:
    st.session_state.custom_same_overrides = {}

is_dark = (st.session_state.theme_mode == "Dark")

# ═══════════════════════════════════════════════════════════════════════════
# ULTRA-COMPACT THEME STYLES (DARK & LIGHT)
# ═══════════════════════════════════════════════════════════════════════════
if is_dark:
    theme_css_vars = """
    :root {
        --bg-main: #0f0e0d;
        --bg-surface: #181512;
        --bg-surface-elevated: #221c17;
        --bg-surface-subtle: #14110e;
        --border-main: #2b231d;
        --border-focus: #f59e0b;
        --border-subtle: #241d18;
        --text-primary: #f5f2ed;
        --text-secondary: #a39788;
        --text-muted: #756a5c;
        --input-bg: #1c1713;
        --input-border: #332921;
        --btn-bg: #221b16;
        --btn-border: #382c22;
        --btn-text: #e8e1d7;
        --btn-hover-bg: #2f251e;
        --btn-hover-border: #524032;
        --btn-hover-text: #ffffff;
        --table-header-bg: #14100d;
        --table-row-hover: #1f1914;
        --table-cell-border: #241c16;
        --badge-amber-bg: rgba(245, 158, 11, 0.12);
        --badge-amber-border: rgba(245, 158, 11, 0.35);
        --badge-amber-text: #fbbf24;
        --badge-purple-bg: rgba(168, 85, 247, 0.14);
        --badge-purple-border: rgba(168, 85, 247, 0.35);
        --badge-purple-text: #c084fc;
        --badge-cyan-bg: rgba(6, 182, 212, 0.12);
        --badge-cyan-border: rgba(6, 182, 212, 0.32);
        --accent-purple: #c084fc;
        --accent-amber: #fbbf24;
        --accent-cyan: #38bdf8;
        --accent-green: #34d399;
        --accent-pink: #f472b6;
        --accent-coral: #fb923c;
        --tab-list-bg: #14100d;
        --tab-active-bg: #261e18;
        --tab-active-border: #47382c;
        --tab-active-text: #fbbf24;
        --card-shadow: 0 1px 2px rgba(0,0,0,0.3);
    }
    """
else:
    theme_css_vars = """
    :root {
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
        --input-bg: #ffffff;
        --input-border: #cbd5e1;
        --btn-bg: #ffffff;
        --btn-border: #cbd5e1;
        --btn-text: #0f172a;
        --btn-hover-bg: #f1f5f9;
        --btn-hover-border: #94a3b8;
        --btn-hover-text: #0f172a;
        --table-header-bg: #f8fafc;
        --table-row-hover: #f1f5f9;
        --table-cell-border: #e2e8f0;
        --badge-amber-bg: #fef3c7;
        --badge-amber-border: #fde68a;
        --badge-amber-text: #b45309;
        --badge-purple-bg: #f3e8ff;
        --badge-purple-border: #d8b4fe;
        --badge-purple-text: #7e22ce;
        --badge-cyan-bg: #e0f2fe;
        --badge-cyan-border: #bae6fd;
        --accent-purple: #7e22ce;
        --accent-amber: #d97706;
        --accent-cyan: #0284c7;
        --accent-green: #059669;
        --accent-pink: #db2777;
        --accent-coral: #ea580c;
        --tab-list-bg: #f1f5f9;
        --tab-active-bg: #ffffff;
        --tab-active-border: #cbd5e1;
        --tab-active-text: #d97706;
        --card-shadow: 0 1px 3px rgba(0, 0, 0, 0.05), 0 1px 2px rgba(0, 0, 0, 0.03);
    }
    """

st.html(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;600;700;800&display=swap');

{theme_css_vars}

/* Zero Horizontal Scroll & High Density Base */
html, body, .stApp, [data-testid="stAppViewContainer"], .block-container {{
    overflow-x: hidden !important;
    max-width: 100vw !important;
    box-sizing: border-box !important;
    background-color: var(--bg-main) !important;
    color: var(--text-primary) !important;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
}}

/* Completely hide Streamlit native top header */
header[data-testid="stHeader"],
[data-testid="stHeader"],
#MainMenu,
footer {{
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
}}

/* Ultra Compact Page Container */
.block-container {{
    max-width: 1400px !important;
    padding-top: 0.5rem !important;
    padding-bottom: 2rem !important;
    padding-left: clamp(0.5rem, 1.8vw, 1.2rem) !important;
    padding-right: clamp(0.5rem, 1.8vw, 1.2rem) !important;
}}

/* Streamlit Gap Reductions for High-Density UI */
[data-testid="stVerticalBlock"] {{
    gap: 0.35rem !important;
}}
div[data-testid="stVerticalBlock"] > div {{
    gap: 0.35rem !important;
}}
div[data-testid="stHorizontalBlock"] {{
    gap: 0.45rem !important;
    align-items: center !important;
}}

/* Section Headers */
.section-tag {{
    font-size: 0.68rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-secondary);
    margin-top: 0.6rem;
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.section-tag::after {{
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border-subtle);
    margin-left: 6px;
}}

/* Top Brand Bar */
.brand-bar {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 12px;
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 8px;
    margin-bottom: 4px;
    box-shadow: var(--card-shadow);
    flex-wrap: wrap;
    gap: 6px;
}}
.brand-left {{
    display: flex;
    align-items: center;
    gap: 8px;
}}
.brand-title {{
    font-size: 0.95rem;
    font-weight: 800;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 6px;
}}
.brand-badge-pro {{
    font-size: 0.62rem;
    font-weight: 800;
    padding: 1px 5px;
    border-radius: 4px;
    background: var(--badge-amber-bg);
    border: 1px solid var(--badge-amber-border);
    color: var(--badge-amber-text);
    text-transform: uppercase;
}}
.brand-sub {{
    font-size: 0.72rem;
    color: var(--text-secondary);
    font-weight: 500;
}}
.brand-chips {{
    display: flex;
    gap: 5px;
    align-items: center;
}}
.chip {{
    padding: 2px 7px;
    border-radius: 5px;
    font-size: 0.68rem;
    font-weight: 700;
}}
.chip-heads {{
    background: var(--badge-amber-bg);
    border: 1px solid var(--badge-amber-border);
    color: var(--badge-amber-text);
}}
.chip-lot {{
    background: var(--badge-purple-bg);
    border: 1px solid var(--badge-purple-border);
    color: var(--badge-purple-text);
}}
.chip-waste {{
    background: var(--badge-cyan-bg);
    border: 1px solid var(--badge-cyan-border);
    color: var(--accent-cyan);
}}

/* Compact Production Toolbar Card */
.toolbar-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 8px;
    padding: 8px 10px;
    margin-bottom: 4px;
    box-shadow: var(--card-shadow);
}}

/* Pipeline Metric Cards Grid */
.pipeline-grid {{
    display: grid;
    grid-template-columns: repeat(6, 1fr);
    gap: 7px;
    margin-bottom: 8px;
}}
.pipe-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 7px;
    padding: 7px 10px;
    position: relative;
    box-shadow: var(--card-shadow);
    transition: transform 0.15s ease, border-color 0.15s ease;
}}
.pipe-card:hover {{
    transform: translateY(-1px);
    border-color: var(--border-focus);
}}
.pipe-card.purple {{ border-top: 3px solid var(--accent-purple); }}
.pipe-card.amber  {{ border-top: 3px solid var(--accent-amber); }}
.pipe-card.cyan   {{ border-top: 3px solid var(--accent-cyan); }}
.pipe-card.green  {{ border-top: 3px solid var(--accent-green); }}
.pipe-card.pink   {{ border-top: 3px solid var(--accent-pink); }}
.pipe-card.coral  {{ border-top: 3px solid var(--accent-coral); }}

.pipe-label {{
    font-size: 0.62rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--text-secondary);
    margin-bottom: 2px;
}}
.pipe-value {{
    font-size: 1.25rem;
    font-weight: 800;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.15;
}}
.pipe-sub {{
    font-size: 0.66rem;
    color: var(--text-muted);
    margin-top: 2px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

/* High Density Cut-Sheet Cards (2 per row on desktop) */
.cut-card {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 7px;
    padding: 7px 10px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    box-shadow: var(--card-shadow);
}}
.cut-title {{
    font-size: 0.8rem;
    font-weight: 700;
    color: var(--text-primary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 220px;
}}
.cut-sub {{
    font-size: 0.68rem;
    color: var(--text-secondary);
    font-family: 'JetBrains Mono', monospace;
}}

/* Compact Data Table */
.data-table-container {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 8px;
    overflow-x: auto;
    margin-bottom: 8px;
    box-shadow: var(--card-shadow);
}}
.data-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
    text-align: left;
}}
.data-table th {{
    background: var(--table-header-bg);
    color: var(--text-secondary);
    font-size: 0.66rem;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 7px 10px;
    border-bottom: 1px solid var(--border-main);
}}
.data-table td {{
    padding: 7px 10px;
    border-bottom: 1px solid var(--table-cell-border);
    color: var(--text-primary);
    vertical-align: middle;
}}
.data-table tr:last-child td {{
    border-bottom: none;
}}
.data-table tr:hover {{
    background: var(--table-row-hover);
}}

/* Badges */
.badge-same-erp {{
    background: var(--badge-purple-bg);
    border: 1px solid var(--badge-purple-border);
    color: var(--accent-purple);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 700;
    display: inline-block;
}}
.badge-common-erp {{
    background: var(--badge-cyan-bg);
    border: 1px solid var(--badge-cyan-border);
    color: var(--accent-cyan);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.68rem;
    font-weight: 700;
    display: inline-block;
}}
.badge-double-erp {{
    background: var(--badge-amber-bg);
    border: 1px solid var(--badge-amber-border);
    color: var(--accent-amber);
    padding: 1px 6px;
    border-radius: 4px;
    font-size: 0.66rem;
    font-weight: 700;
    display: inline-block;
}}

/* Surface Container */
.card-surface {{
    background: var(--bg-surface);
    border: 1px solid var(--border-main);
    border-radius: 8px;
    padding: 10px 12px;
    margin-bottom: 8px;
    box-shadow: var(--card-shadow);
}}
.mini-box {{
    background: var(--bg-surface-elevated);
    border: 1px solid var(--border-main);
    border-radius: 5px;
    padding: 6px 4px;
    text-align: center;
}}

/* ═══════════════════════════════════════════════════════════════════
   ULTRA-COMPACT STREAMLIT INPUTS OVERRIDES
   ═══════════════════════════════════════════════════════════════════ */
.stNumberInput, .stTextInput, .stSelectbox {{
    margin-bottom: 0px !important;
}}
[data-testid="stNumberInputContainer"],
div[data-baseweb="base-input"],
div[data-baseweb="input"],
div[data-baseweb="select"] > div,
div[data-testid="stSelectbox"] [data-baseweb="select"] {{
    background-color: var(--input-bg) !important;
    border: 1px solid var(--input-border) !important;
    border-radius: 5px !important;
    color: var(--text-primary) !important;
    min-height: 28px !important;
    height: 28px !important;
    padding: 0 4px !important;
}}
[data-testid="stNumberInput"] input,
[data-testid="stTextInput"] input,
input {{
    background-color: var(--input-bg) !important;
    color: var(--text-primary) !important;
    -webkit-text-fill-color: var(--text-primary) !important;
    height: 26px !important;
    font-size: 0.78rem !important;
    padding: 1px 4px !important;
    font-family: 'JetBrains Mono', monospace !important;
}}

button[data-testid="stNumberInputStepDown"],
button[data-testid="stNumberInputStepUp"],
[data-testid="stNumberInputStepDown"],
[data-testid="stNumberInputStepUp"] {{
    background-color: var(--bg-surface-elevated) !important;
    border: none !important;
    color: var(--text-primary) !important;
    width: 20px !important;
    height: 24px !important;
    min-width: 20px !important;
    padding: 0 !important;
}}
button[data-testid="stNumberInputStepDown"] svg,
button[data-testid="stNumberInputStepUp"] svg {{
    fill: var(--text-primary) !important;
    stroke: var(--text-primary) !important;
    width: 10px !important;
    height: 10px !important;
}}

/* All Buttons (Compact) */
button,
button[kind="secondary"],
button[kind="primary"],
[data-testid^="stBaseButton"],
.stButton > button,
.stDownloadButton > button {{
    background-color: var(--btn-bg) !important;
    border: 1px solid var(--btn-border) !important;
    color: var(--btn-text) !important;
    border-radius: 5px !important;
    height: 28px !important;
    min-height: 28px !important;
    padding: 2px 8px !important;
    font-size: 0.74rem !important;
    font-weight: 600 !important;
    box-shadow: var(--card-shadow) !important;
}}
button p, button span, button div {{
    color: var(--btn-text) !important;
    font-size: 0.74rem !important;
}}
button:hover, .stButton > button:hover {{
    background-color: var(--btn-hover-bg) !important;
    border-color: var(--border-focus) !important;
    color: var(--btn-hover-text) !important;
}}
button:hover p, button:hover span, button:hover div {{
    color: var(--btn-hover-text) !important;
}}

/* Compact Labels */
[data-testid="stWidgetLabel"] {{
    min-height: auto !important;
    margin-bottom: 1px !important;
}}
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] label {{
    color: var(--text-secondary) !important;
    font-weight: 700 !important;
    font-size: 0.65rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    margin: 0 !important;
}}

/* File Uploader Dropzone */
[data-testid="stFileUploader"] section,
section[data-testid="stFileUploadDropzone"] {{
    background-color: var(--bg-surface) !important;
    border: 1px dashed var(--border-main) !important;
    border-radius: 6px !important;
    padding: 4px 8px !important;
    min-height: 40px !important;
}}
section[data-testid="stFileUploadDropzone"] button {{
    height: 24px !important;
    min-height: 24px !important;
    font-size: 0.68rem !important;
    padding: 1px 6px !important;
}}
section[data-testid="stFileUploadDropzone"] small,
section[data-testid="stFileUploadDropzone"] span {{
    font-size: 0.68rem !important;
}}

/* Radio Buttons */
[data-testid="stRadio"] label p,
[data-testid="stRadio"] label span {{
    color: var(--text-primary) !important;
    font-size: 0.74rem !important;
}}

/* Tab List */
[data-baseweb="tab-list"] {{
    background: var(--tab-list-bg) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 7px !important;
    padding: 2px !important;
    gap: 3px !important;
    margin-bottom: 8px !important;
}}
[data-baseweb="tab"] {{
    background: transparent !important;
    border: none !important;
    border-radius: 5px !important;
    font-size: 0.74rem !important;
    font-weight: 700 !important;
    color: var(--text-secondary) !important;
    padding: 4px 10px !important;
}}
[aria-selected="true"] {{
    background: var(--tab-active-bg) !important;
    border: 1px solid var(--tab-active-border) !important;
    color: var(--tab-active-text) !important;
    box-shadow: var(--card-shadow) !important;
}}

/* Expander */
[data-testid="stExpander"] {{
    background: var(--bg-surface) !important;
    border: 1px solid var(--border-main) !important;
    border-radius: 6px !important;
    margin-top: 4px !important;
}}
[data-testid="stExpander"] summary {{
    padding: 4px 8px !important;
    font-size: 0.74rem !important;
}}

/* Responsive Breakpoints */
@media (max-width: 1024px) {{
    .pipeline-grid {{
        grid-template-columns: repeat(3, 1fr) !important;
    }}
}}
@media (max-width: 640px) {{
    .pipeline-grid {{
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 5px !important;
    }}
    .pipe-card {{
        padding: 6px 8px !important;
    }}
    .pipe-value {{
        font-size: 1.1rem !important;
    }}
}}
</style>
""")

active_theme_str = "dark" if is_dark else "light"
saved_h = st.session_state.saved_heads
saved_l = f"{st.session_state.saved_lots:g}"
saved_s = st.session_state.saved_shades
saved_w = f"{st.session_state.saved_waste:.1f}"
saved_r = f"{st.session_state.saved_rate:.2f}"

st.html(f"""
<script>
(function() {{
    try {{
        var currentUrl = new URL(window.location.href);
        var storedRaw = localStorage.getItem("threadworks_settings");
        var stored = storedRaw ? JSON.parse(storedRaw) : null;

        // Auto-fix corrupted rate from previous sessions
        if (stored && (stored.rate === "1.45" || parseFloat(stored.rate) > 5.0 || parseFloat(stored.rate) < 0.05)) {{
            stored.rate = "0.45";
            localStorage.setItem("threadworks_settings", JSON.stringify(stored));
        }}

        if (currentUrl.searchParams.get("rate") === "1.45") {{
            currentUrl.searchParams.set("rate", "0.45");
            window.location.replace(currentUrl.toString());
            return;
        }}

        var activeTheme = "{active_theme_str}";
        var activeHeads = "{saved_h}";
        var activeLots = "{saved_l}";
        var activeShades = "{saved_s}";
        var activeWaste = "{saved_w}";
        var activeRate = "{saved_r}";
        if (activeRate === "1.45") {{ activeRate = "0.45"; }}

        // Save active values to localStorage
        var toSave = {{
            theme: activeTheme,
            heads: activeHeads,
            lots: activeLots,
            shades: activeShades,
            waste: activeWaste,
            rate: activeRate
        }};
        localStorage.setItem("threadworks_settings", JSON.stringify(toSave));
        localStorage.setItem("threadworks_theme", activeTheme);

        // If user visits bare URL without query params, restore their saved settings from browser
        if (stored && typeof stored === "object") {{
            var needsRedirect = false;
            var keys = ["theme", "heads", "lots", "shades", "waste", "rate"];
            for (var i = 0; i < keys.length; i++) {{
                var k = keys[i];
                var valToSet = stored[k];
                if (k === "rate" && (valToSet === "1.45" || parseFloat(valToSet) > 5.0)) {{
                    valToSet = "0.45";
                }}
                if (!currentUrl.searchParams.has(k) && valToSet !== undefined && valToSet !== null) {{
                    currentUrl.searchParams.set(k, valToSet);
                    needsRedirect = true;
                }}
            }}
            if (needsRedirect) {{
                window.location.replace(currentUrl.toString());
            }}
        }}
    }} catch(e) {{}}
}})();
</script>
""")

# ═══════════════════════════════════════════════════════════════════════════
# TOP BRAND BAR & THEME SWITCHER
# ═══════════════════════════════════════════════════════════════════════════
col_hdr_main, col_hdr_theme = st.columns([8.2, 1.8])

with col_hdr_main:
    st.html(f"""
    <div class="brand-bar">
        <div class="brand-left">
            <span style="font-size:1.2rem;">🧵</span>
            <div>
                <div class="brand-title">
                    THREADWORKS
                    <span class="brand-badge-pro">ERP v2.4</span>
                </div>
                <div class="brand-sub">Factory Production & Cones Requisition Engine</div>
            </div>
        </div>
        <div class="brand-chips">
            <span class="chip chip-heads">⚡ {saved_h} Heads</span>
            <span class="chip chip-lot">🎨 {saved_s} Colors / Lot</span>
            <span class="chip chip-waste">🎯 {saved_l} Lot</span>
        </div>
    </div>
    """)

with col_hdr_theme:
    selected_theme = st.radio(
        "Theme",
        ["☀️ Light", "🌙 Dark"],
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
# COMPACT TOOLBAR: FILE UPLOAD & CONTROLS
# ═══════════════════════════════════════════════════════════════════════════
c_up_file, c_up_clear = st.columns([8.8, 1.2])

with c_up_file:
    uploaded_files = st.file_uploader(
        "Upload Wilcom PDF / Design Images:",
        type=["pdf", "png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
        key=f"file_uploader_{st.session_state.uploader_key}",
        label_visibility="collapsed"
    )

with c_up_clear:
    if st.button("🗑️ Clear", use_container_width=True, help="Remove all parts"):
        st.session_state.parts = {}
        st.session_state.custom_same_overrides = {}
        st.session_state.uploader_key += 1
        st.rerun()

# Handle Uploaded Files
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
        if ext == "pdf":
            try:
                parsed_parts = parse_wilcom_pdf(c, fname)
                if isinstance(parsed_parts, dict):
                    parsed_parts = [parsed_parts]
                for idx, part_data in enumerate(parsed_parts):
                    sub_h = f"{h}_{idx}" if len(parsed_parts) > 1 else h
                    if sub_h not in st.session_state.parts:
                        part_data["hash"] = sub_h
                        if "heads" not in part_data:
                            is_double = (
                                part_data.get("repeat", 1.0) >= 2.0 or
                                part_data.get("is_double_repeat", False) or
                                bool(re.search(r'\b(double|14\s*h|14\s*head)\b', f"{fname} {part_data.get('design_name', '')}", re.I))
                            )
                            part_data["heads"] = max(1, st.session_state.saved_heads // 2) if is_double else st.session_state.saved_heads
                        st.session_state.parts[sub_h] = part_data
            except Exception as e:
                st.error(f"PDF error {fname}: {e}")
        else:
            if h not in st.session_state.parts:
                try:
                    data = parse_image_part(c, fname)
                    data["hash"] = h
                    if "heads" not in data:
                        is_double = (
                            data.get("repeat", 1.0) >= 2.0 or
                            data.get("is_double_repeat", False) or
                            bool(re.search(r'\b(double|14\s*h|14\s*head)\b', f"{fname} {data.get('design_name', '')}", re.I))
                        )
                        data["heads"] = max(1, st.session_state.saved_heads // 2) if is_double else st.session_state.saved_heads
                    st.session_state.parts[h] = data
                except Exception as e:
                    st.error(f"Image error {fname}: {e}")

if not st.session_state.parts:
    st.html("""
    <div style="background:var(--bg-surface); border:1px dashed var(--border-main); border-radius:8px; padding:24px 16px; text-align:center; color:var(--text-secondary); margin:8px 0; box-shadow:var(--card-shadow);">
        <div style="font-size:2rem; margin-bottom:6px;">📁</div>
        <div style="font-weight:700; font-size:0.95rem; color:var(--text-primary); margin-bottom:4px;">Koi Worksheet Upload Nahi Hui</div>
        <div style="font-size:0.8rem; max-width:520px; margin:0 auto; line-height:1.5; margin-bottom:12px;">Upar apni Wilcom PDF production worksheet ya design images upload karein taake cut-sheet aur cones calculation shuru ho sakay.</div>
    </div>
    """)
    c_dm1, c_dm2, c_dm3 = st.columns([1, 1.8, 1])
    with c_dm2:
        if st.button("✨ Load Factory Demo Data (ZB-1149 Suit)", use_container_width=True):
            st.session_state.parts = get_demo_parts(default_heads=st.session_state.saved_heads)
            st.rerun()
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# COMPACT PRODUCTION PARAMETERS RIBBON
# ═══════════════════════════════════════════════════════════════════════════
st.html('<div class="section-tag">PRODUCTION PARAMETERS</div>')

cp1, cp2, cp3, cp4, cp5, cp6 = st.columns([1.5, 1.5, 2.4, 2.0, 1.4, 1.2])

with cp1:
    machine_heads = st.number_input(
        "HEADS",
        min_value=1,
        max_value=120,
        value=st.session_state.saved_heads,
        step=1,
        help="Machine heads (Default: 28)"
    )
    if machine_heads != st.session_state.saved_heads:
        old_h = st.session_state.saved_heads
        st.session_state.saved_heads = machine_heads
        st.query_params["heads"] = str(machine_heads)
        if "parts" in st.session_state:
            for p in st.session_state.parts.values():
                if p.get("heads") == old_h:
                    p["heads"] = machine_heads
        st.rerun()

with cp2:
    base_colors_count = st.number_input(
        "BASE SHADES",
        min_value=1,
        max_value=30,
        value=st.session_state.saved_shades,
        step=1,
        help="Base cloth colors per lot (Default: 6)"
    )
    if base_colors_count != st.session_state.saved_shades:
        st.session_state.saved_shades = base_colors_count
        st.query_params["shades"] = str(base_colors_count)

pieces_per_lot = machine_heads * base_colors_count

with cp3:
    col_q_mode, col_q_val = st.columns([1.1, 1.3])
    with col_q_mode:
        lots_mode = st.radio("MODE", ["Lots", "Pcs"], index=0, horizontal=True)
    with col_q_val:
        if lots_mode == "Lots":
            lots_count = st.number_input(
                "TOTAL LOTS",
                min_value=0.5,
                max_value=50.0,
                value=st.session_state.saved_lots,
                step=0.5,
                help="Total Lots (Default: 1.0)"
            )
            if lots_count != st.session_state.saved_lots:
                st.session_state.saved_lots = lots_count
                st.query_params["lots"] = f"{lots_count:g}"
            num_pieces = int(round(pieces_per_lot * lots_count))
        else:
            num_pieces = st.number_input(
                "TOTAL PCS",
                min_value=1,
                max_value=100000,
                value=int(round(pieces_per_lot * st.session_state.saved_lots)),
                step=machine_heads
            )
            lots_count = round(num_pieces / pieces_per_lot, 2)

with cp4:
    col_u_type, col_u_val = st.columns([1.0, 1.4])
    with col_u_type:
        cone_unit = st.selectbox("UNIT", ["Meters", "Yards"], index=0)
    with col_u_val:
        default_cap = DEFAULT_CONE_CAPACITY_METERS if "Meters" in cone_unit else DEFAULT_CONE_CAPACITY_YARDS
        cone_capacity_val = st.number_input("CAPACITY", min_value=100.0, max_value=50000.0, value=default_cap, step=100.0)

with cp5:
    waste_pct = st.number_input(
        "WASTE %",
        min_value=0.0,
        max_value=30.0,
        value=st.session_state.saved_waste,
        step=1.0,
        format="%.1f",
        help="Dhaaga wastage (Auto: 0%)"
    )
    if waste_pct != st.session_state.saved_waste:
        st.session_state.saved_waste = waste_pct
        st.query_params["waste"] = f"{waste_pct:.1f}"

with cp6:
    stitch_rate = st.number_input(
        "RATE/1K (Rs)",
        min_value=0.05,
        max_value=5.0,
        value=st.session_state.saved_rate,
        step=0.05,
        format="%.2f",
        help="Stitching rate per 1,000 stitches in PKR (Factory default: 0.45 Rs / 1k st)"
    )
    if stitch_rate != st.session_state.saved_rate:
        st.session_state.saved_rate = stitch_rate
        st.query_params["rate"] = f"{stitch_rate:.2f}"

# One-line Summary Banner
suits_per_color_calc = int(round(num_pieces / max(1, base_colors_count)))
runs_per_color_calc = round(suits_per_color_calc / max(1, machine_heads), 1)
def_h = max(1, machine_heads)
total_runs_preview = sum(
    math.ceil(float(p.get("repeat", 1.0)) * (num_pieces / def_h))
    for p in st.session_state.parts.values()
) if st.session_state.parts else math.ceil(num_pieces / machine_heads)

st.html(f"""
<div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:6px; padding:4px 10px; font-size:0.72rem; color:var(--text-secondary); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:4px; margin-bottom:4px;">
    <span>📦 <strong>Order:</strong> <span style="color:var(--text-primary);">{num_pieces} Suits</span> ({lots_count:g} Lots)</span>
    <span>⚡ <strong>Machine:</strong> {machine_heads} Heads → <strong>{total_runs_preview} Total Repeat</strong></span>
    <span>🎨 <strong>Har Color:</strong> <span style="color:var(--accent-amber); font-weight:700;">{suits_per_color_calc} Suits</span> ({runs_per_color_calc:g} Repeat / color)</span>
    <span>🧵 <strong>Cone Size:</strong> {cone_capacity_val:,.0f} {cone_unit} (Wastage: {waste_pct:.0f}%)</span>
</div>
""")

with st.expander("⚙️ Advanced Machine Speeds & Options (Optional)"):
    ca1, ca2, ca3 = st.columns(3)
    with ca1:
        machine_rpm = st.number_input("Machine RPM", min_value=300, max_value=1200, value=DEFAULT_MACHINE_RPM, step=25)
    with ca2:
        shift_hours = st.selectbox("Shift Hours", [8.0, 10.0, 12.0], index=0)
    with ca3:
        include_boring = st.checkbox("Include Boring Tool", value=False)
    cone_price = DEFAULT_CONE_PRICE


# ═══════════════════════════════════════════════════════════════════════════
# HIGH-DENSITY CUT-SHEET (SIDE-BY-SIDE 2-COLUMNS ACROSS WIDTH)
# ═══════════════════════════════════════════════════════════════════════════
st.html('<div class="section-tag" style="margin-top:0.4rem;">PARTS CUT-SHEET & REPEATS</div>')

part_keys = list(st.session_state.parts.keys())
to_delete = None

total_preview_st = sum(
    int(round(p['stitches'] * (float(p.get('repeat', 1.0)) * (int(p.get('heads', def_h)) / def_h))))
    for p in st.session_state.parts.values()
)
total_order_runs_preview = sum(
    math.ceil(float(p.get("repeat", 1.0)) * (num_pieces / def_h))
    for p in st.session_state.parts.values()
)

# Cut-sheet Header Bar
st.html(f"""
<div style="display:flex; justify-content:space-between; align-items:center; background:var(--bg-surface); border:1px solid var(--border-main); border-radius:6px; padding:5px 10px; margin-bottom:5px; font-size:0.74rem; flex-wrap:wrap; gap:4px;">
    <span>Components: <strong style="color:var(--text-primary);">{len(part_keys)} Parts</strong></span>
    <span>1 Suit: <strong style="color:var(--accent-amber); font-family:'JetBrains Mono',monospace;">{total_preview_st:,} st</strong></span>
    <span>Grand Stitches ({num_pieces} Suits): <strong style="color:var(--accent-cyan); font-family:'JetBrains Mono',monospace;">{total_preview_st * num_pieces:,} st</strong></span>
    <span>Kul Machine Chakar: <strong style="color:var(--accent-green); font-family:'JetBrains Mono',monospace;">{total_order_runs_preview} Total Repeat</strong></span>
</div>
""")

# 2 Parts Side-by-Side per row on desktop (1 doosray k samnay)
for i in range(0, len(part_keys), 2):
    col_c_left, col_c_right = st.columns(2)

    # Left Part
    h_l = part_keys[i]
    p_l = st.session_state.parts[h_l]
    badge_l = "IMG" if p_l.get("is_image") else "PDF"
    cur_rep_l = float(p_l.get("repeat", 1.0))
    cur_heads_l = int(p_l.get("heads", machine_heads))
    if cur_heads_l <= 0:
        cur_heads_l = machine_heads

    with col_c_left:
        c_info, c_in_rep, c_in_heads, c_in_sub, c_in_del = st.columns([3.3, 1.7, 1.7, 2.7, 0.6])
        with c_info:
            is_dbl_l = (cur_heads_l < machine_heads) or (cur_rep_l >= 2.0) or ("double" in p_l.get("design_name", "").lower())
            dbl_notice_l = f'<span class="badge-double-erp">⚡ {cur_heads_l}H Double</span>' if is_dbl_l else ""
            st.html(f"""
            <div style="padding-top:2px;">
                <span class="badge-common-erp">{badge_l}</span> {dbl_notice_l}
                <div style="font-size:0.78rem; font-weight:700; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:180px;" title="{p_l['design_name']}">{p_l['design_name']}</div>
                <div style="font-size:0.68rem; color:var(--text-secondary); font-family:'JetBrains Mono',monospace;">{p_l['stitches']:,} st</div>
            </div>
            """)
        with c_in_rep:
            st.html('<div style="font-size:0.60rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">REPEAT</div>')
            new_rep_l = st.number_input(
                f"R_{h_l}",
                min_value=0.1,
                max_value=20.0,
                value=cur_rep_l,
                step=0.5,
                format="%.1f",
                key=f"rep_g_{h_l}",
                label_visibility="collapsed",
                help="Repeat (Chakar per suit)"
            )
            st.session_state.parts[h_l]["repeat"] = new_rep_l
        with c_in_heads:
            st.html('<div style="font-size:0.60rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">HEADS</div>')
            new_heads_l = st.number_input(
                f"H_{h_l}",
                min_value=1,
                max_value=120,
                value=cur_heads_l,
                step=1,
                key=f"heads_g_{h_l}",
                label_visibility="collapsed",
                help="Active Heads (maslan 14 heads for double repeat)"
            )
            st.session_state.parts[h_l]["heads"] = new_heads_l
        with c_in_sub:
            def_h = max(1, machine_heads)
            suit_mult_l = new_rep_l * (new_heads_l / def_h)
            st_calc_l = int(round(p_l['stitches'] * suit_mult_l))
            p_runs_l = math.ceil(new_rep_l * (num_pieces / def_h))
            p_runs_clr_l = round(new_rep_l * (suits_per_color_calc / def_h), 1)
            st.html(f"""
            <div style="padding-top:2px;">
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; font-weight:800; color:var(--accent-amber);">
                    = {st_calc_l:,} st
                </div>
                <div style="font-size:0.68rem; color:var(--accent-cyan); font-weight:700;">
                    {p_runs_l} Repeat <span style="font-size:0.62rem; color:var(--text-secondary); font-weight:normal;">({p_runs_clr_l:g}/clr)</span>
                </div>
            </div>
            """)
        with c_in_del:
            st.html('<div style="height:12px;"></div>')
            if st.button("✕", key=f"del_g_{h_l}", help=f"Remove {p_l['design_name']}"):
                to_delete = h_l

    # Right Part (if exists)
    if i + 1 < len(part_keys):
        h_r = part_keys[i + 1]
        p_r = st.session_state.parts[h_r]
        badge_r = "IMG" if p_r.get("is_image") else "PDF"
        cur_rep_r = float(p_r.get("repeat", 1.0))
        cur_heads_r = int(p_r.get("heads", machine_heads))
        if cur_heads_r <= 0:
            cur_heads_r = machine_heads

        with col_c_right:
            c_info_r, c_in_rep_r, c_in_heads_r, c_in_sub_r, c_in_del_r = st.columns([3.3, 1.7, 1.7, 2.7, 0.6])
            with c_info_r:
                is_dbl_r = (cur_heads_r < machine_heads) or (cur_rep_r >= 2.0) or ("double" in p_r.get("design_name", "").lower())
                dbl_notice_r = f'<span class="badge-double-erp">⚡ {cur_heads_r}H Double</span>' if is_dbl_r else ""
                st.html(f"""
                <div style="padding-top:2px;">
                    <span class="badge-same-erp">{badge_r}</span> {dbl_notice_r}
                    <div style="font-size:0.78rem; font-weight:700; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:180px;" title="{p_r['design_name']}">{p_r['design_name']}</div>
                    <div style="font-size:0.68rem; color:var(--text-secondary); font-family:'JetBrains Mono',monospace;">{p_r['stitches']:,} st</div>
                </div>
                """)
            with c_in_rep_r:
                st.html('<div style="font-size:0.60rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">REPEAT</div>')
                new_rep_r = st.number_input(
                    f"R_{h_r}",
                    min_value=0.1,
                    max_value=20.0,
                    value=cur_rep_r,
                    step=0.5,
                    format="%.1f",
                    key=f"rep_g_{h_r}",
                    label_visibility="collapsed",
                    help="Repeat (Chakar per suit)"
                )
                st.session_state.parts[h_r]["repeat"] = new_rep_r
            with c_in_heads_r:
                st.html('<div style="font-size:0.60rem; color:var(--text-muted); font-weight:700; text-transform:uppercase;">HEADS</div>')
                new_heads_r = st.number_input(
                    f"H_{h_r}",
                    min_value=1,
                    max_value=120,
                    value=cur_heads_r,
                    step=1,
                    key=f"heads_g_{h_r}",
                    label_visibility="collapsed",
                    help="Active Heads (maslan 14 heads for double repeat)"
                )
                st.session_state.parts[h_r]["heads"] = new_heads_r
            with c_in_sub_r:
                def_h = max(1, machine_heads)
                suit_mult_r = new_rep_r * (new_heads_r / def_h)
                st_calc_r = int(round(p_r['stitches'] * suit_mult_r))
                p_runs_r = math.ceil(new_rep_r * (num_pieces / def_h))
                p_runs_clr_r = round(new_rep_r * (suits_per_color_calc / def_h), 1)
                st.html(f"""
                <div style="padding-top:2px;">
                    <div style="font-family:'JetBrains Mono',monospace; font-size:0.78rem; font-weight:800; color:var(--accent-amber);">
                        = {st_calc_r:,} st
                    </div>
                    <div style="font-size:0.68rem; color:var(--accent-cyan); font-weight:700;">
                        {p_runs_r} Repeat <span style="font-size:0.62rem; color:var(--text-secondary); font-weight:normal;">({p_runs_clr_r:g}/clr)</span>
                    </div>
                </div>
                """)
            with c_in_del_r:
                st.html('<div style="height:12px;"></div>')
                if st.button("✕", key=f"del_g_{h_r}", help=f"Remove {p_r['design_name']}"):
                    to_delete = h_r

if to_delete and to_delete in st.session_state.parts:
    del st.session_state.parts[to_delete]
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTION ENGINE CALCULATION
# ═══════════════════════════════════════════════════════════════════════════
total_suit_stitches, total_suit_sequins, total_suit_bobbin_m, colors_dict = aggregate_suit_parts(
    st.session_state.parts,
    include_boring=include_boring if 'include_boring' in locals() else False,
    default_heads=machine_heads
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
    cone_price=cone_price if 'cone_price' in locals() else DEFAULT_CONE_PRICE,
    machine_rpm=machine_rpm if 'machine_rpm' in locals() else DEFAULT_MACHINE_RPM,
    shift_hours=shift_hours if 'shift_hours' in locals() else DEFAULT_SHIFT_HOURS,
    parts=st.session_state.parts
)

cone_rows = results["cone_rows"]
total_order_cones = results["total_order_cones"]
total_common_cones = results["total_common_cones"]
total_same_cones = results["total_same_cones"]
suits_per_base_color = results["suits_per_base_color"]
frames_per_base_color = results["frames_per_base_color"]
total_runs = results["total_runs"]
shifts_needed = results["shifts_needed"]
days_needed = results["days_needed"]
cost_per_suit = results["cost_per_suit"]
total_order_cost = results["total_order_cost"]
stitching_cost_suit = results["stitching_cost_suit"]
piece_rate = results.get("piece_rate", stitching_cost_suit)
total_order_amount = results.get("total_order_amount", total_order_cost)
thread_cost_suit = results["thread_cost_suit"]
bobbin_cost_suit = results["bobbin_cost_suit"]
total_dhaaga_suit = thread_cost_suit + bobbin_cost_suit


# ═══════════════════════════════════════════════════════════════════════════
# COMPACT PIPELINE METRIC CARDS
# ═══════════════════════════════════════════════════════════════════════════
st.html('<div class="section-tag">PRODUCTION PIPELINE KPI</div>')

same_per_color_count = int(round(total_same_cones / max(1, base_colors_count)))

st.html(f"""
<div class="pipeline-grid">
    <div class="pipe-card purple">
        <div class="pipe-label">KUL DHAAGA</div>
        <div class="pipe-value" style="color:var(--accent-purple);">{total_order_cones}</div>
        <div class="pipe-sub">{total_same_cones} Same + {total_common_cones} Common</div>
    </div>
    <div class="pipe-card amber">
        <div class="pipe-label">TOTAL PRODUCTION</div>
        <div class="pipe-value" style="color:var(--accent-amber);">{num_pieces}</div>
        <div class="pipe-sub">{lots_count:g} Lots · {total_runs} Repeat</div>
    </div>
    <div class="pipe-card cyan">
        <div class="pipe-label">MACHINE SHIFTS</div>
        <div class="pipe-value" style="color:var(--accent-cyan);">{shifts_needed}</div>
        <div class="pipe-sub">~{days_needed} Din (@ 2 shifts)</div>
    </div>
    <div class="pipe-card green">
        <div class="pipe-label">1 PIECE RATE</div>
        <div class="pipe-value" style="color:var(--accent-green);">Rs {piece_rate:,.2f}</div>
        <div class="pipe-sub">{total_suit_stitches:,} st @ Rs {stitch_rate:.2f}/1k</div>
    </div>
    <div class="pipe-card pink">
        <div class="pipe-label">SAME / COLOR</div>
        <div class="pipe-value" style="color:var(--accent-pink);">{same_per_color_count}</div>
        <div class="pipe-sub">Cones/shade ({suits_per_base_color} pcs)</div>
    </div>
    <div class="pipe-card coral">
        <div class="pipe-label">STITCHES / SUIT</div>
        <div class="pipe-value" style="color:var(--accent-coral);">{total_suit_stitches // 1000}k</div>
        <div class="pipe-sub">{total_suit_stitches:,} st total</div>
    </div>
</div>
""")


# ═══════════════════════════════════════════════════════════════════════════
# TABS (DHAAGA REQUISITION, 3-LEVEL, COSTING, MASTER SLIP)
# ═══════════════════════════════════════════════════════════════════════════
tab_req, tab_levels, tab_cost, tab_slip = st.tabs([
    "🏪 STORE REQUISITION",
    "📊 3-LEVEL BREAKDOWN",
    "💰 1 PIECE RATE & BILLING",
    "📋 MASTER JOB SLIP"
])


# ───────────────────────────────────────────────────────────────────────────
# TAB 1: STORE REQUISITION (MATCHING USER REFERENCE DESIGN)
# ───────────────────────────────────────────────────────────────────────────
with tab_req:
    st.html(f"""
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; flex-wrap:wrap; gap:4px; font-size:0.75rem; color:var(--text-secondary);">
        <span>Order: <strong style="color:var(--text-primary);">{num_pieces} Suits</strong> ({lots_count:g} Lots) | Machine: <strong style="color:var(--text-primary);">{machine_heads} Heads</strong> | Base Colors: <strong style="color:var(--text-primary);">{base_colors_count}</strong> ({suits_per_base_color} pcs/color) | 1 Cone: <strong style="color:var(--text-primary);">{cone_capacity_val:,.0f} {cone_unit}</strong></span>
    </div>
    """)

    if cone_rows:
        df_cones = pd.DataFrame(cone_rows).sort_values("Kul Cones (🧵)", ascending=False)

        table_html = """<div class="data-table-container">
<table class="data-table">
<thead>
<tr>
<th style="width:35px;">N#</th>
<th>CODE</th>
<th>DESCRIPTION</th>
<th>TYPE</th>
<th>1 SUIT (M)</th>
<th>CONES / SUIT</th>
<th>HAR COLOR CONES</th>
<th style="color:var(--accent-amber);">KUL CONES</th>
<th>FORMULA / DETAIL</th>
</tr>
</thead>
<tbody>"""

        for _, r in df_cones.iterrows():
            is_same = r.get("Is_Same", False)
            badge_html = f'<span class="badge-same-erp">Same</span>' if is_same else f'<span class="badge-common-erp">Common</span>'
            color_accent = "var(--accent-purple)" if is_same else "var(--accent-cyan)"

            table_html += f"""<tr>
<td style="color:var(--text-muted); font-family:'JetBrains Mono',monospace;">{r['Needle']}</td>
<td style="font-weight:700; color:{color_accent};">{r['Code']}</td>
<td>{r['Description']}</td>
<td>{badge_html}</td>
<td style="font-family:'JetBrains Mono',monospace;">{r['1 Suit (m)']} m</td>
<td style="font-family:'JetBrains Mono',monospace; color:var(--text-secondary);">{r['Cones / Suit']}</td>
<td style="font-weight:600;">{r['Per Color Cones']}</td>
<td style="font-weight:800; color:var(--accent-amber); font-family:'JetBrains Mono',monospace; font-size:0.9rem;">{r['Kul Cones (🧵)']} 🧵</td>
<td style="color:var(--text-secondary); font-size:0.72rem;">{r['Formula / Note']}</td>
</tr>"""

        table_html += """</tbody>
</table>
</div>"""
        st.html(table_html)

        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.download_button(
                "📥 Requisition CSV",
                df_cones.to_csv(index=False).encode("utf-8-sig"),
                f"Requisition_{num_pieces}_suits.csv",
                "text/csv",
                use_container_width=True
            )
        with col_d2:
            store_summary_text = f"🧵 *DHAAGA REQUISITION ({num_pieces} Suits / {lots_count:g} Lots)*\n"
            store_summary_text += f"Machine: *{machine_heads} Heads* | Base Colors: *{base_colors_count}* ({suits_per_base_color} pcs/color)\n"
            store_summary_text += f"1 Cone = {cone_capacity_val:,.0f} {cone_unit} (Waste: {waste_pct:.0f}%)\n\n"
            for _, r in df_cones.iterrows():
                store_summary_text += f"• Code {r['Code']} ({r['Description']}) [{r['Category']}]: *{r['Kul Cones (🧵)']} Cones* ({r['Formula / Note']})\n"
            store_summary_text += f"\n*KUL CONES:* {total_order_cones} Cones\n*Total Repeat:* {total_runs}"

            st.download_button(
                "📋 WhatsApp Slip Text",
                store_summary_text,
                f"WhatsApp_{num_pieces}_suits.txt",
                "text/plain",
                use_container_width=True
            )


# ───────────────────────────────────────────────────────────────────────────
# TAB 2: 3-LEVEL BREAKDOWN (COMPACT 2-COLUMN SIDE-BY-SIDE GRID)
# ───────────────────────────────────────────────────────────────────────────
with tab_levels:
    waste_mult = 1.0 + (waste_pct / 100.0)
    color_keys = list(colors_dict.keys())

    # Display 2 colors side-by-side on desktop
    for i in range(0, len(color_keys), 2):
        col_l2_left, col_l2_right = st.columns(2)

        # Left Color
        c_code_l = color_keys[i]
        info_l = colors_dict[c_code_l]
        m_suit_l = info_l["meters_1_suit"]
        yd_suit_l = m_suit_l * METERS_TO_YARDS
        is_same_l = info_l["is_same"]

        if "Yards" in cone_unit:
            c_per_suit_l = yd_suit_l / cone_capacity_val if cone_capacity_val > 0 else 0
            c_color_l = (yd_suit_l * suits_per_base_color * waste_mult) / cone_capacity_val if cone_capacity_val > 0 else 0
            c_lot_l = (yd_suit_l * num_pieces * waste_mult) / cone_capacity_val if cone_capacity_val > 0 else 0
        else:
            c_per_suit_l = m_suit_l / cone_capacity_val if cone_capacity_val > 0 else 0
            c_color_l = (m_suit_l * suits_per_base_color * waste_mult) / cone_capacity_val if cone_capacity_val > 0 else 0
            c_lot_l = (m_suit_l * num_pieces * waste_mult) / cone_capacity_val if cone_capacity_val > 0 else 0

        badge_l = f'<span class="badge-same-erp">Same ({suits_per_base_color} pcs)</span>' if is_same_l else f'<span class="badge-common-erp">Common ({num_pieces} pcs)</span>'
        color_acc_l = "var(--accent-purple)" if is_same_l else "var(--accent-cyan)"

        with col_l2_left:
            st.html(f"""
            <div class="card-surface">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <div>
                        <span style="color:var(--text-muted); font-family:'JetBrains Mono',monospace; font-size:0.7rem;">N#{info_l['needle']}</span>
                        <strong style="color:{color_acc_l}; margin-left:4px; font-size:0.85rem;">{info_l['code']}</strong>
                        <span style="color:var(--text-secondary); font-size:0.75rem; margin-left:4px;">({info_l['name']})</span>
                    </div>
                    <div>{badge_l}</div>
                </div>
                <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; text-align:center;">
                    <div class="mini-box">
                        <span style="font-size:0.6rem; color:var(--text-secondary); font-weight:800; text-transform:uppercase;">1 SHIRT</span>
                        <div style="font-size:0.85rem; font-weight:800; color:var(--text-primary);">{m_suit_l:.1f} m</div>
                        <span style="font-size:0.65rem; color:var(--accent-amber);">{c_per_suit_l:.3f} c</span>
                    </div>
                    <div class="mini-box">
                        <span style="font-size:0.6rem; color:var(--text-secondary); font-weight:800; text-transform:uppercase;">HAR COLOR</span>
                        <div style="font-size:0.85rem; font-weight:800; color:var(--accent-cyan);">{math.ceil(c_color_l) if is_same_l else math.ceil(c_lot_l)} Cones</div>
                        <span style="font-size:0.65rem; color:var(--text-secondary);">{c_color_l:.1f} exact</span>
                    </div>
                    <div class="mini-box" style="border-color:var(--border-focus);">
                        <span style="font-size:0.6rem; color:var(--accent-amber); font-weight:800; text-transform:uppercase;">TOTAL CONES</span>
                        <div style="font-size:0.95rem; font-weight:800; color:var(--accent-amber);">
                            {math.ceil(c_color_l) * base_colors_count if is_same_l else math.ceil(c_lot_l)} 🧵
                        </div>
                        <span style="font-size:0.65rem; color:var(--text-secondary);">
                            {f"{base_colors_count} × {math.ceil(c_color_l)}" if is_same_l else "Poori Lot"}
                        </span>
                    </div>
                </div>
            </div>
            """)

        # Right Color (if exists)
        if i + 1 < len(color_keys):
            c_code_r = color_keys[i + 1]
            info_r = colors_dict[c_code_r]
            m_suit_r = info_r["meters_1_suit"]
            yd_suit_r = m_suit_r * METERS_TO_YARDS
            is_same_r = info_r["is_same"]

            if "Yards" in cone_unit:
                c_per_suit_r = yd_suit_r / cone_capacity_val if cone_capacity_val > 0 else 0
                c_color_r = (yd_suit_r * suits_per_base_color * waste_mult) / cone_capacity_val if cone_capacity_val > 0 else 0
                c_lot_r = (yd_suit_r * num_pieces * waste_mult) / cone_capacity_val if cone_capacity_val > 0 else 0
            else:
                c_per_suit_r = m_suit_r / cone_capacity_val if cone_capacity_val > 0 else 0
                c_color_r = (m_suit_r * suits_per_base_color * waste_mult) / cone_capacity_val if cone_capacity_val > 0 else 0
                c_lot_r = (m_suit_r * num_pieces * waste_mult) / cone_capacity_val if cone_capacity_val > 0 else 0

            badge_r = f'<span class="badge-same-erp">Same ({suits_per_base_color} pcs)</span>' if is_same_r else f'<span class="badge-common-erp">Common ({num_pieces} pcs)</span>'
            color_acc_r = "var(--accent-purple)" if is_same_r else "var(--accent-cyan)"

            with col_l2_right:
                st.html(f"""
                <div class="card-surface">
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                        <div>
                            <span style="color:var(--text-muted); font-family:'JetBrains Mono',monospace; font-size:0.7rem;">N#{info_r['needle']}</span>
                            <strong style="color:{color_acc_r}; margin-left:4px; font-size:0.85rem;">{info_r['code']}</strong>
                            <span style="color:var(--text-secondary); font-size:0.75rem; margin-left:4px;">({info_r['name']})</span>
                        </div>
                        <div>{badge_r}</div>
                    </div>
                    <div style="display:grid; grid-template-columns:repeat(3, 1fr); gap:6px; text-align:center;">
                        <div class="mini-box">
                            <span style="font-size:0.6rem; color:var(--text-secondary); font-weight:800; text-transform:uppercase;">1 SHIRT</span>
                            <div style="font-size:0.85rem; font-weight:800; color:var(--text-primary);">{m_suit_r:.1f} m</div>
                            <span style="font-size:0.65rem; color:var(--accent-amber);">{c_per_suit_r:.3f} c</span>
                        </div>
                        <div class="mini-box">
                            <span style="font-size:0.6rem; color:var(--text-secondary); font-weight:800; text-transform:uppercase;">HAR COLOR</span>
                            <div style="font-size:0.85rem; font-weight:800; color:var(--accent-cyan);">{math.ceil(c_color_r) if is_same_r else math.ceil(c_lot_r)} Cones</div>
                            <span style="font-size:0.65rem; color:var(--text-secondary);">{c_color_r:.1f} exact</span>
                        </div>
                        <div class="mini-box" style="border-color:var(--border-focus);">
                            <span style="font-size:0.6rem; color:var(--accent-amber); font-weight:800; text-transform:uppercase;">TOTAL CONES</span>
                            <div style="font-size:0.95rem; font-weight:800; color:var(--accent-amber);">
                                {math.ceil(c_color_r) * base_colors_count if is_same_r else math.ceil(c_lot_r)} 🧵
                            </div>
                            <span style="font-size:0.65rem; color:var(--text-secondary);">
                                {f"{base_colors_count} × {math.ceil(c_color_r)}" if is_same_r else "Poori Lot"}
                            </span>
                        </div>
                    </div>
                </div>
                """)


# ───────────────────────────────────────────────────────────────────────────
# ───────────────────────────────────────────────────────────────────────────
# TAB 3: 1 PIECE RATE & ORDER BILLING
# ───────────────────────────────────────────────────────────────────────────
with tab_cost:
    col_fc1, col_fc2 = st.columns([1.1, 0.9])

    with col_fc1:
        # Part-by-part breakdown rows
        parts_rows_html = ""
        def_h = max(1, machine_heads)
        for h, p in st.session_state.parts.items():
            rep = float(p.get('repeat', 1.0))
            heads = int(p.get('heads', machine_heads))
            suit_mult = rep * (heads / def_h)
            p_runs = math.ceil(rep * (num_pieces / def_h))
            p_st_single = int(round(p.get('stitches', 0)))
            p_st_total = int(round(p_st_single * suit_mult))
            p_cost = (p_st_total / 1000.0) * stitch_rate
            dbl_badge = ' <span class="badge-double-erp">Double</span>' if heads < machine_heads else ""
            parts_rows_html += f"""
            <tr style="border-bottom:1px solid var(--border-main);">
                <td style="padding:6px 4px;">
                    <strong style="color:var(--text-primary);">{p.get('design_name', 'Part')}</strong>{dbl_badge}
                    <div style="font-size:0.68rem; color:var(--text-secondary);">{p_st_single:,} st × {rep:g} rep</div>
                </td>
                <td style="text-align:center; font-family:'JetBrains Mono',monospace; padding:6px 4px; color:var(--text-primary);">
                    {heads} H
                </td>
                <td style="text-align:center; font-family:'JetBrains Mono',monospace; font-weight:700; padding:6px 4px; color:var(--accent-cyan);">
                    {p_runs}
                </td>
                <td style="text-align:right; font-family:'JetBrains Mono',monospace; padding:6px 4px; color:var(--text-secondary);">
                    {p_st_total:,} st
                </td>
                <td style="text-align:right; font-family:'JetBrains Mono',monospace; font-weight:700; padding:6px 4px; color:var(--accent-amber);">
                    Rs {p_cost:,.2f}
                </td>
            </tr>
            """

        st.html(f"""
        <div class="card-surface">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                <span style="font-size:0.75rem; font-weight:800; text-transform:uppercase; color:var(--accent-amber);">
                    🧵 1 PIECE RATE (STITCHING RATE)
                </span>
                <span style="font-size:0.7rem; color:var(--accent-cyan); font-weight:700;">
                    Formula: (Tankay × Rate) ÷ 1,000
                </span>
            </div>

            <!-- Big Formula Banner -->
            <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-focus); border-radius:8px; padding:10px 14px; margin-bottom:12px;">
                <div style="font-size:0.72rem; color:var(--text-secondary); margin-bottom:4px; text-transform:uppercase; font-weight:700;">
                    Formula & Calculation:
                </div>
                <div style="font-size:0.92rem; font-family:'JetBrains Mono',monospace; color:var(--text-primary);">
                    (<strong>{total_suit_stitches:,}</strong> stitches × Rs <strong>{stitch_rate:.2f}</strong>) ÷ 1,000
                </div>
                <div style="font-size:1.6rem; font-weight:900; color:var(--accent-green); font-family:'JetBrains Mono',monospace; margin-top:6px;">
                    = Rs {piece_rate:,.2f} <span style="font-size:0.85rem; font-weight:700; color:var(--text-secondary);">/ Piece</span>
                </div>
            </div>

            <!-- Parts Breakdown Table -->
            <div style="font-size:0.72rem; font-weight:800; color:var(--text-secondary); text-transform:uppercase; margin-bottom:6px;">
                SUIT KE PARTS KA RATE BREAKDOWN:
            </div>
            <table style="width:100%; border-collapse:collapse; font-size:0.78rem;">
                <thead>
                    <tr style="border-bottom:1.5px solid var(--border-focus); color:var(--text-secondary); text-align:left; font-size:0.68rem; text-transform:uppercase;">
                        <th style="padding:4px;">Part</th>
                        <th style="text-align:center; padding:4px;">Heads</th>
                        <th style="text-align:center; padding:4px;">Repeat</th>
                        <th style="text-align:right; padding:4px;">Stitches</th>
                        <th style="text-align:right; padding:4px;">Rate (Rs)</th>
                    </tr>
                </thead>
                <tbody>
                    {parts_rows_html}
                    <tr style="background:var(--bg-surface-elevated); font-weight:900; border-top:2px solid var(--border-focus); font-size:0.85rem;">
                        <td colspan="2" style="padding:8px 4px; color:var(--accent-green);">1 PIECE KUL RATE:</td>
                        <td style="text-align:center; padding:8px 4px; font-family:'JetBrains Mono',monospace; color:var(--accent-cyan); font-weight:800;">{total_runs} Repeat</td>
                        <td style="text-align:right; padding:8px 4px; font-family:'JetBrains Mono',monospace; color:var(--text-primary);">
                            {total_suit_stitches:,} st
                        </td>
                        <td style="text-align:right; padding:8px 4px; font-family:'JetBrains Mono',monospace; color:var(--accent-green); font-size:1.05rem;">
                            Rs {piece_rate:,.2f}
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
        """)

    with col_fc2:
        profit_pct = st.slider("MUNAFA / PROFIT MARGIN (%)", min_value=0, max_value=50, value=0, step=5)
        
        quoted_piece_rate = piece_rate * (1.0 + (profit_pct / 100.0))
        quoted_order_total = quoted_piece_rate * num_pieces

        margin_card_html = ""
        if profit_pct > 0:
            margin_card_html = f"""
            <div style="background:var(--bg-surface-elevated); border:1px solid var(--accent-amber); border-radius:8px; padding:10px 12px; margin-top:10px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:0.72rem; font-weight:800; color:var(--accent-amber); text-transform:uppercase;">CLIENT QUOTATION (+{profit_pct}%)</span>
                    <span style="font-size:0.8rem; font-weight:900; color:var(--accent-green);">+{profit_pct}% Munafa</span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:4px;">
                    <span style="font-size:0.75rem; color:var(--text-secondary);">Quoted 1 Piece Rate:</span>
                    <strong style="font-size:1.1rem; font-weight:900; color:var(--accent-amber); font-family:'JetBrains Mono',monospace;">
                        Rs {quoted_piece_rate:,.2f} / Piece
                    </strong>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:2px;">
                    <span style="font-size:0.75rem; color:var(--text-secondary);">Quoted Order Bill:</span>
                    <strong style="font-size:1.15rem; font-weight:900; color:var(--accent-green); font-family:'JetBrains Mono',monospace;">
                        Rs {quoted_order_total:,.0f}
                    </strong>
                </div>
                <div style="font-size:0.68rem; color:var(--text-secondary); text-align:right; margin-top:2px;">
                    Kul Munafa: <strong style="color:var(--accent-green);">Rs {quoted_order_total - total_order_amount:,.0f}</strong>
                </div>
            </div>
            """

        st.html(f"""
        <div class="card-surface">
            <div style="font-size:0.75rem; font-weight:800; text-transform:uppercase; color:var(--accent-cyan); margin-bottom:10px;">
                📦 POORI LOT / ORDER BILL
            </div>

            <!-- Total Order Box -->
            <div style="background:var(--bg-surface-elevated); border:1px solid var(--border-main); border-radius:8px; padding:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:0.72rem; font-weight:700; color:var(--text-secondary); text-transform:uppercase;">
                        ORDER QUANTITY:
                    </span>
                    <span style="font-size:0.85rem; font-weight:800; color:var(--accent-amber);">
                        {num_pieces} Pieces ({lots_count:g} Lots)
                    </span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:0.72rem; font-weight:700; color:var(--text-secondary); text-transform:uppercase;">
                        1 PIECE RATE:
                    </span>
                    <span style="font-size:0.95rem; font-weight:800; font-family:'JetBrains Mono',monospace; color:var(--accent-purple);">
                        Rs {piece_rate:,.2f}
                    </span>
                </div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
                    <span style="font-size:0.72rem; font-weight:700; color:var(--text-secondary); text-transform:uppercase;">
                        GRAND TOTAL STITCHES:
                    </span>
                    <span style="font-size:0.85rem; font-weight:800; font-family:'JetBrains Mono',monospace; color:var(--text-primary);">
                        {total_suit_stitches * num_pieces:,} st
                    </span>
                </div>
                
                <hr style="border:0; border-top:1px dashed var(--border-focus); margin:8px 0;" />
                
                <div style="display:flex; justify-content:space-between; align-items:baseline;">
                    <span style="font-size:0.82rem; font-weight:800; color:var(--accent-green); text-transform:uppercase;">
                        POORI LOT KUL BILL:
                    </span>
                    <strong style="font-size:1.4rem; font-weight:900; color:var(--accent-green); font-family:'JetBrains Mono',monospace;">
                        Rs {total_order_amount:,.0f}
                    </strong>
                </div>
                <div style="font-size:0.68rem; color:var(--text-secondary); text-align:right; margin-top:2px;">
                    {num_pieces} Pieces × Rs {piece_rate:,.2f}
                </div>
            </div>

            {margin_card_html}
        </div>
        """)


# ───────────────────────────────────────────────────────────────────────────
# TAB 4: MASTER JOB SLIP
# ───────────────────────────────────────────────────────────────────────────
with tab_slip:
    master_slip_text = f"""============================================================
              EMBROIDERY JOB SLIP & CONES REQUISITION
============================================================
Order: {num_pieces} Suits ({lots_count:g} Lots) | Machine: {machine_heads} Heads
Base Colors: {base_colors_count} Colors ({suits_per_base_color} pcs / color) | Total Machine Repeats: {total_runs}
Total Stitches per Suit: {total_suit_stitches:,}
Grand Stitches: {total_suit_stitches * num_pieces:,}
Rate/1k St: Rs {stitch_rate:.2f} | 1 Piece Rate: Rs {piece_rate:,.2f} | Kul Order Bill: Rs {total_order_amount:,.0f}
Andazan Waqt: {shifts_needed} Shifts (~{days_needed} Din @ 2 shifts/day)
1 Cone Capacity: {cone_capacity_val:,.0f} {cone_unit} | Wastage: {waste_pct:.0f}%
============================================================
SUIT KE PARTS (CUT-SHEET):
"""
    def_h = max(1, machine_heads)
    for h, p in st.session_state.parts.items():
        rep = float(p.get('repeat', 1.0))
        heads = int(p.get('heads', machine_heads))
        suit_mult = rep * (heads / def_h)
        p_runs = math.ceil(rep * (num_pieces / def_h))
        p_st = int(round(p.get('stitches', 0) * suit_mult))
        p_c = (p_st / 1000.0) * stitch_rate
        dbl_tag = " [Double Repeat]" if heads < machine_heads else ""
        master_slip_text += f"- {p['design_name']:<30} : Rep {rep:g}x | {heads} Heads ({p_runs} Repeat){dbl_tag} | {p_st:,} st -> Rs {p_c:,.2f}\n"

    master_slip_text += f"""------------------------------------------------------------
DHAAGA REQUISITION (STORE / PURCHASE):
"""
    for _, r in df_cones.iterrows():
        master_slip_text += f"• Code {r['Code']:<8} {r['Description'][:18]:<18} [{r['Category'][:10]}]: {r['Kul Cones (🧵)']:>3} Cones ({r['Formula / Note']})\n"

    master_slip_text += f"""============================================================
1 PIECE RATE: Rs {piece_rate:,.2f}  |  KUL ORDER BILL ({num_pieces} pcs): Rs {total_order_amount:,.0f}
KUL CONES: {total_order_cones} Cones
============================================================
Master Signature: _______________   Store Issue: ___________
"""

    st.text_area("Master Slip Text", master_slip_text, height=220)

    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.download_button(
            "📥 Slip Download (.txt)",
            master_slip_text,
            f"Job_Slip_{num_pieces}_suits.txt",
            "text/plain",
            use_container_width=True
        )
    with col_s2:
        whatsapp_msg = f"🧵 *EMBROIDERY JOB SLIP ({num_pieces} Suits / {lots_count:g} Lots)*\n"
        whatsapp_msg += f"Machine: *{machine_heads} Heads* | Base Colors: *{base_colors_count}* ({suits_per_base_color} pcs/color)\n"
        whatsapp_msg += f"Stitches / Suit: *{total_suit_stitches:,}*\n"
        whatsapp_msg += f"*1 Piece Rate:* Rs {piece_rate:,.2f} (@ Rs {stitch_rate:.2f} / 1k st)\n"
        whatsapp_msg += f"*Kul Order Bill ({num_pieces} pcs):* Rs {total_order_amount:,.0f}\n"
        whatsapp_msg += f"1 Cone = {cone_capacity_val:,.0f} {cone_unit} (Waste: {waste_pct:.0f}%)\n\n"
        whatsapp_msg += "*SUIT KE PARTS (CUT-SHEET):*\n"
        def_h = max(1, machine_heads)
        for h, p in st.session_state.parts.items():
            rep = float(p.get('repeat', 1.0))
            heads = int(p.get('heads', machine_heads))
            p_runs = math.ceil(rep * (num_pieces / def_h))
            dbl_str = " (Double Repeat)" if heads < machine_heads else ""
            whatsapp_msg += f"• *{p['design_name']}*: Rep {rep:g}x | *{heads} Heads* ({p_runs} Repeat){dbl_str}\n"
        whatsapp_msg += "\n*DHAAGA LIST:*\n"
        for _, r in df_cones.iterrows():
            whatsapp_msg += f"- *Code {r['Code']}* ({r['Description']}): *{r['Kul Cones (🧵)']} Cones* ({r['Formula / Note']})\n"
        whatsapp_msg += f"\n*KUL CONES:* {total_order_cones} Cones\n"
        whatsapp_msg += f"*Total Repeat:* {total_runs} Repeats (~{shifts_needed} Shifts)"

        st.download_button(
            "📲 WhatsApp Format (.txt)",
            whatsapp_msg,
            f"WhatsApp_{num_pieces}_suits.txt",
            "text/plain",
            use_container_width=True
        )
