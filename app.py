"""
Threadworks — Embroidery Production Calculator
Run: python -m streamlit run app.py --server.maxUploadSize 20
"""
import io
import re
import math
import hashlib
import pdfplumber
import pandas as pd
import streamlit as st

# ═══════════════════════════════════════════════════════════════════════════
# CONFIG & CSS
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="Threadworks • Calculator", page_icon="🧵", layout="wide")

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

.stApp {
    font-family: 'Inter', sans-serif;
}
.block-container { max-width: 1200px; padding-top: 2rem; }

/* Metrics */
[data-testid="stMetric"] {
    background: var(--secondary-background-color);
    border: 1px solid rgba(128, 128, 128, 0.2);
    border-radius: 12px;
    padding: 16px 20px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.05);
    transition: transform 0.2s, border-color 0.2s;
}
[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 16px rgba(0,0,0,0.1);
    border-color: #087f72;
}
[data-testid="stMetricLabel"] {
    font-weight: 600 !important;
    text-transform: uppercase;
    font-size: 11px !important;
    letter-spacing: 0.05em;
    opacity: 0.8;
}
[data-testid="stMetricValue"] {
    font-weight: 800 !important;
    font-size: 1.8rem !important;
}

/* Tables */
[data-testid="stDataFrame"] {
    border-radius: 12px;
    border: 1px solid rgba(128, 128, 128, 0.2);
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

/* Titles */
h1, h2, h3 { letter-spacing: -0.02em; }
.section-title { 
    font-size: 1.2rem; 
    font-weight: 700; 
    margin-bottom: 12px; 
    border-bottom: 2px solid rgba(128, 128, 128, 0.2); 
    padding-bottom: 8px; 
}
</style>""", unsafe_allow_html=True)

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 30


# ═══════════════════════════════════════════════════════════════════════════
# PDF PARSING LOGIC
# ═══════════════════════════════════════════════════════════════════════════
def extract_worksheet(upload):
    raw = upload.getvalue()
    if len(raw) > MAX_BYTES:
        raise ValueError("File exceeds 20 MB limit.")
    
    full_text = ""
    with pdfplumber.open(io.BytesIO(raw)) as pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise ValueError("PDF exceeds 30 pages.")
        for page in pdf.pages:
            full_text += (page.extract_text(layout=True) or '') + "\n"

    # Design Name
    dm = re.search(r'Design:\s*(.+?)(?:\n|$)', full_text)
    design_name = dm.group(1).strip() if dm else upload.name.replace('.pdf', '').strip()

    # Repeat (e.g. "1 R", "Half R", "1+Half R")
    m = re.search(r'\(\s*(\d+)?\s*\+?\s*(half)?\s*r\s*\)', design_name, re.I)
    repeat = 1.0
    if m:
        whole = int(m.group(1)) if m.group(1) else 0
        half = 0.5 if m.group(2) else 0.0
        repeat = whole + half if (whole + half) > 0 else 1.0

    # Stitches
    sm = re.search(r'Stitches:\s*([\d,]+)', full_text)
    stitches = int(sm.group(1).replace(',', '')) if sm else 0

    # Thread Usage Total
    tu_match = re.search(r'Thread\s+usage:\s*([\d,]+(?:\.\d+)?)\s*(m|ft)', full_text, re.I)
    thread_usage_val = 0.0
    if tu_match:
        thread_usage_val = float(tu_match.group(1).replace(',', ''))
        if tu_match.group(2).lower() in ('ft', 'feet'):
            thread_usage_val *= 0.3048  # Feet to Meters

    # Thread Colors (Filtering out Boring/Same)
    nu_section = re.split(r'N#\s+Color\s+Name\s+Length', full_text, flags=re.I)
    usage_colors = []
    if len(nu_section) > 1:
        usage_text = nu_section[-1]
        color_matches = re.findall(
            r'(\d+)\.\s+(\S+)\s*(.*?)\s+([\d,]+(?:\.\d+)?)\s*(m|ft)',
            usage_text, re.I
        )
        for seq, code, name, length, unit in color_matches:
            c_code = code.strip()
            c_name = name.strip()
            
            # Skip boring and same
            if c_code.lower() in ('boring', 'same') or c_name.lower() in ('boring', 'same'):
                continue
                
            length_val = float(length.replace(',', ''))
            if unit.lower() in ('ft', 'feet'):
                length_val *= 0.3048
                
            usage_colors.append({
                'seq': int(seq),
                'code': c_code,
                'name': c_name if c_name else c_code,
                'length_m': round(length_val, 2),
            })
            
    # Sequins count
    sequin_section = re.search(r'Sequins:.*?#\s*Shape\s*Size\s*Count\s*Name(.*?)(?:Thread usage:|$)', full_text, re.I | re.DOTALL)
    sequin_count = 0
    if sequin_section:
        for line in sequin_section.group(1).split('\n'):
            line = line.strip()
            if not line: continue
            parts = line.split()
            # Match lines like "1. 3.0 668" -> looking for a dot after number
            if len(parts) >= 3 and parts[0].endswith('.'):
                try:
                    sequin_count += int(parts[2].replace(',', ''))
                except ValueError:
                    pass

    return {
        'filename': upload.name,
        'design_name': design_name,
        'repeat': repeat,
        'stitches': stitches,
        'thread_usage_m': round(thread_usage_val, 2),
        'colors': usage_colors,
        'sequin_count': sequin_count,
        'raw_text': full_text,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SIDEBAR SETTINGS
# ═══════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.image("https://api.iconify.design/lucide:scissors.svg?color=%23087f72", width=40)
    st.title("Settings")
    st.markdown("---")
    
    st.subheader("📦 Order Quantity")
    num_pieces = st.number_input("Total Suits (Pieces)", min_value=1, value=1, step=1)
    
    st.subheader("⏱️ Machine Settings")
    machine_heads = st.number_input("Machine Heads", min_value=1, value=28, step=1, help="Number of heads on the machine (pieces made at one time)")
    stitches_per_shift = st.number_input("Stitches / Shift", min_value=10000, value=500000, step=10000, help="Machine capacity per head in one shift")
    shift_hours = st.number_input("Shift Duration (Hours)", min_value=1.0, value=8.0, step=0.5)
    
    st.subheader("🧵 Thread & Cone")
    meters_per_cone = st.number_input("Meters per Cone", min_value=100.0, value=2770.0, step=10.0)
    waste_pct = st.number_input("Thread Waste (%)", min_value=0.0, value=10.0, step=1.0)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN INTERFACE
# ═══════════════════════════════════════════════════════════════════════════
st.title("🧵 Embroidery Production Calculator")
st.markdown("Upload all PDF parts of a suit. The app automatically groups them, extracts lengths (converting feet to meters), ignores 'boring/same', and calculates combined thread usage.")

if 'raw_parts' not in st.session_state:
    st.session_state.raw_parts = {}
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

uploads = st.file_uploader("Drop Wilcom PDF Worksheets", type=['pdf'], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}", label_visibility="collapsed")

col1, col2 = st.columns([1, 6])
if col1.button("🗑️ Clear All"):
    st.session_state.raw_parts = {}
    st.session_state.uploader_key += 1
    st.rerun()

if uploads:
    new_parts = {}
    for upload in uploads:
        file_hash = hashlib.sha256(upload.getvalue()).hexdigest()
        if file_hash not in st.session_state.raw_parts:
            try:
                data = extract_worksheet(upload)
                data['hash'] = file_hash
                new_parts[file_hash] = data
            except Exception as e:
                st.error(f"Error reading {upload.name}: {e}")
        else:
            new_parts[file_hash] = st.session_state.raw_parts[file_hash]
    st.session_state.raw_parts = new_parts

if not st.session_state.raw_parts:
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# DATA PROCESSING & DISPLAY
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>1. Adjust Repeats (Multiplies Stitches & Thread)</div>", unsafe_allow_html=True)

# Build dataframe for editor
df_data = []
for h, part in st.session_state.raw_parts.items():
    df_data.append({
        'Hash': h,
        'Filename': part['filename'],
        'Part Name': part['design_name'],
        'Base Stitches': part['stitches'],
        'Sequins': part['sequin_count'],
        'Repeat': part['repeat'],
    })
df = pd.DataFrame(df_data)

# Editable table
edited_df = st.data_editor(
    df,
    key="parts_editor",
    hide_index=True,
    use_container_width=True,
    disabled=['Hash', 'Filename', 'Part Name', 'Base Stitches', 'Sequins'],
    column_config={
        'Hash': None,  # Hide
        'Repeat': st.column_config.NumberColumn(
            "Repeat ×",
            min_value=0.1,
            max_value=50.0,
            step=0.5,
            format="%.1f",
            help="Multiplier for both stitches and thread lengths"
        )
    }
)

# ── Aggregate Totals ──
total_suit_stitches = 0
total_suit_sequins = 0
aggregated_colors = {}

for _, row in edited_df.iterrows():
    h = row['Hash']
    repeat = row['Repeat']
    part = st.session_state.raw_parts[h]
    
    total_suit_stitches += part['stitches'] * repeat
    total_suit_sequins += part['sequin_count'] * repeat
    
    for c in part['colors']:
        code = c['code']
        if code not in aggregated_colors:
            aggregated_colors[code] = {'name': c['name'], 'length_m': 0.0}
        aggregated_colors[code]['length_m'] += c['length_m'] * repeat

grand_stitches = total_suit_stitches * num_pieces
grand_sequins = total_suit_sequins * num_pieces

total_runs = math.ceil(num_pieces / machine_heads)
total_machine_stitches = total_runs * total_suit_stitches
shifts_needed = total_machine_stitches / stitches_per_shift if stitches_per_shift > 0 else 0
shifts_needed = round(shifts_needed, 2)


st.markdown("<br><div class='section-title'>2. Production Totals</div>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("🔢 Total Stitches (All Suits)", f"{grand_stitches:,}", f"{total_suit_stitches:,} / suit")
c2.metric("✨ Total Sequins", f"{grand_sequins:,}", f"{total_suit_sequins:,} / suit")
c3.metric("⏱️ Shifts Required", f"{shifts_needed:,}", f"{total_runs} runs on {machine_heads}-head machine")
c4.metric("📦 Order Quantity", f"{num_pieces:,} Suit(s)")


st.markdown("<br><div class='section-title'>3. Thread & Cone Breakdown</div>", unsafe_allow_html=True)

if not aggregated_colors:
    st.warning("No thread color data found in the uploaded files.")
else:
    color_data = []
    grand_thread_m = 0.0
    total_cones = 0
    
    for code, info in aggregated_colors.items():
        per_suit = info['length_m']
        total_len = per_suit * num_pieces
        with_waste = total_len * (1 + waste_pct / 100)
        cones = math.ceil(with_waste / meters_per_cone)
        
        grand_thread_m += with_waste
        total_cones += cones
        
        color_data.append({
            'Color Code': code,
            'Color Name': info['name'],
            'Per Suit (m)': round(per_suit, 2),
            f'Total {num_pieces} Suits (m)': round(total_len, 2),
            f'With {waste_pct:.0f}% Waste (m)': round(with_waste, 2),
            'Cones Required': cones
        })

    color_df = pd.DataFrame(color_data).sort_values('Cones Required', ascending=False)
    
    st.dataframe(
        color_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Cones Required": st.column_config.NumberColumn(
                "Cones Required",
                help=f"Based on {meters_per_cone}m per cone"
            )
        }
    )
    
    sc1, sc2 = st.columns(2)
    sc1.info(f"**Total Thread Needed (with waste):** {grand_thread_m:,.2f} meters")
    sc2.success(f"**Total Cones Needed:** {total_cones:,} cones")
    
    st.download_button(
        "📥 Download Thread Report (CSV)",
        color_df.to_csv(index=False).encode('utf-8-sig'),
        'thread_cone_report.csv',
        'text/csv',
    )
