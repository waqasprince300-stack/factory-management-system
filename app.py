"""
Threadworks — Asaan Embroidery Production & Cones Calculator
Designed for Factory Operations & Machine Masters
"""
import io
import re
import math
import hashlib
import glob
import os
import pandas as pd
import streamlit as st
import pdfplumber

# ═══════════════════════════════════════════════════════════════════════════
# PAGE CONFIGURATION & CLEAN STYLES
# ═══════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Embroidery Calculator • Threadworks",
    page_icon="🧵",
    layout="wide",
    initial_sidebar_state="collapsed"  # Start clean with main focus on center
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', sans-serif;
}

.block-container {
    max-width: 1100px;
    padding-top: 1.2rem;
    padding-bottom: 3rem;
}

/* Header Banner */
.main-header {
    background: linear-gradient(135deg, #0f766e 0%, #0d9488 100%);
    border-radius: 14px;
    padding: 20px 24px;
    color: white;
    margin-bottom: 20px;
    box-shadow: 0 4px 15px rgba(13, 148, 136, 0.15);
}
.main-header h1 {
    font-size: 1.6rem;
    font-weight: 800;
    margin: 0;
    color: white !important;
    display: flex;
    align-items: center;
    gap: 10px;
}
.main-header p {
    font-size: 0.9rem;
    margin: 6px 0 0 0;
    opacity: 0.92;
}

/* Big Highlight Cards */
.result-card {
    background: var(--secondary-background-color);
    border: 1px solid rgba(13, 148, 136, 0.25);
    border-radius: 14px;
    padding: 18px 20px;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.result-card:hover {
    transform: translateY(-2px);
    border-color: #0d9488;
}
.result-label {
    font-size: 0.8rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #0f766e;
    margin-bottom: 6px;
}
.result-value {
    font-size: 1.85rem;
    font-weight: 800;
    color: #0f766e;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.1;
}
.result-sub {
    font-size: 0.78rem;
    color: gray;
    margin-top: 6px;
    font-weight: 500;
}

/* Section Header */
.step-header {
    font-size: 1.1rem;
    font-weight: 700;
    color: #0f766e;
    margin-top: 1.2rem;
    margin-bottom: 0.8rem;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 2px solid rgba(13, 148, 136, 0.18);
    padding-bottom: 6px;
}

/* Badge */
.status-badge {
    background: rgba(13, 148, 136, 0.12);
    color: #0f766e;
    padding: 3px 10px;
    border-radius: 12px;
    font-weight: 700;
    font-size: 0.75rem;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# ACCURATE PDF PARSER (WILCOM WORKSHEETS)
# ═══════════════════════════════════════════════════════════════════════════
def parse_wilcom_pdf(file_bytes, filename=""):
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        if len(pdf.pages) == 0:
            raise ValueError("Empty PDF file.")
        p = pdf.pages[0]
        words = p.extract_words()
        full_text = p.extract_text(layout=False) or ""

        # Design Name
        dm = re.search(r'Design:\s*(.*?)(?:\n|$)', full_text)
        design_name = dm.group(1).strip() if dm else filename.replace(".pdf", "")

        # Stitches
        sm = re.search(r'Stitches:\s*([\d,]+)', full_text)
        stitches = int(sm.group(1).replace(",", "")) if sm else 0

        # Dimensions
        hm = re.search(r'Height:\s*([\d\.]+)\s*mm', full_text)
        height_mm = float(hm.group(1)) if hm else 0.0
        wm = re.search(r'Width:\s*([\d\.]+)\s*mm', full_text)
        width_mm = float(wm.group(1)) if wm else 0.0

        # Bobbin
        tb_m = re.search(r'Total bobbin:\s*([\d\.]+)\s*(m|ft)', full_text, re.I)
        total_bobbin_m = float(tb_m.group(1)) if tb_m else 0.0
        if tb_m and tb_m.group(2).lower() in ("ft", "feet"):
            total_bobbin_m *= 0.3048

        # Auto-detect Repeat (e.g. "1 R", "Half R", "2 R")
        repeat = 1.0
        rep_m = re.search(r'\(\s*(\d+(?:\.\d+)?|\bhalf\b)?\s*(?:\+?\s*(half))?\s*r\s*\)', design_name, re.I)
        if rep_m:
            p1 = rep_m.group(1) or ""
            p2 = rep_m.group(2) or ""
            r_val = 0.0
            if p1.lower() == "half":
                r_val += 0.5
            elif p1:
                try:
                    r_val += float(p1)
                except ValueError:
                    pass
            if p2.lower() == "half":
                r_val += 0.5
            if r_val > 0:
                repeat = r_val

        # Sequins Count
        seq_hdr = next((w for w in words if w["text"] == "Sequins:" and w["x0"] > 380), None)
        tu_hdr = next((w for w in words if w["text"] == "Thread" and w["x0"] > 380 and (not seq_hdr or w["top"] > seq_hdr["top"])), None)
        n_sharp = next((w for w in words if w["text"] == "N#" and w["x0"] > 380), None)

        sequins_total = 0
        if seq_hdr:
            max_top = tu_hdr["top"] if tu_hdr else (seq_hdr["top"] + 120)
            sq_words = [w for w in words if w["x0"] >= seq_hdr["x0"] - 8 and seq_hdr["top"] < w["top"] < max_top]
            sq_lines = []
            curr = []
            for w in sorted(sq_words, key=lambda x: (x["top"], x["x0"])):
                if not curr or abs(w["top"] - curr[0]["top"]) < 5:
                    curr.append(w)
                else:
                    sq_lines.append(curr)
                    curr = [w]
            if curr:
                sq_lines.append(curr)

            for line in sq_lines:
                txt = " ".join(w["text"] for w in line)
                if "#" in txt and "Shape" in txt:
                    continue
                m = re.search(r'^\s*(\d+)\.\s*(?:([A-Za-z]+)\s+)?([\d\.]+)\s+([\d,]+)', txt)
                if m:
                    sequins_total += int(m.group(4).replace(",", ""))
                else:
                    digits = re.findall(r'[\d,]+(?:\.\d+)?', txt)
                    if len(digits) >= 2:
                        try:
                            sequins_total += int(digits[-1].replace(",", ""))
                        except ValueError:
                            pass

        # Thread Colors Table (Right Column Spatial Bounding Box)
        thread_colors = []
        if n_sharp:
            min_x = n_sharp["x0"] - 8
            th_words = [w for w in words if w["x0"] >= min_x and w["top"] > n_sharp["top"] and w["top"] < 760]
            th_lines = []
            curr = []
            for w in sorted(th_words, key=lambda x: (x["top"], x["x0"])):
                if not curr or abs(w["top"] - curr[0]["top"]) < 6:
                    curr.append(w)
                else:
                    th_lines.append(curr)
                    curr = [w]
            if curr:
                th_lines.append(curr)

            for line in th_lines:
                txt = " ".join(w["text"] for w in line)
                if "page" in txt.lower() or "printed" in txt.lower() or "author" in txt.lower():
                    continue
                m = re.search(r'^\s*(\d+)\.\s+(\S+)\s*(.*?)\s+([\d,]+(?:\.\d+)?)\s*(m|ft)', txt, re.I)
                if m:
                    needle = int(m.group(1))
                    code = m.group(2).strip()
                    name = m.group(3).strip()
                    length = float(m.group(4).replace(",", ""))
                    unit = m.group(5).lower()
                    if unit in ("ft", "feet"):
                        length *= 0.3048
                    thread_colors.append({
                        "needle": needle,
                        "code": code,
                        "name": name if name else code,
                        "length_m": round(length, 2)
                    })

        return {
            "filename": filename,
            "design_name": design_name,
            "repeat": repeat,
            "stitches": stitches,
            "height_mm": height_mm,
            "width_mm": width_mm,
            "total_bobbin_m": round(total_bobbin_m, 2),
            "sequins_total": sequins_total,
            "thread_colors": thread_colors,
        }


# ═══════════════════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════
if "parts" not in st.session_state:
    st.session_state.parts = {}
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0


# ═══════════════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="main-header">
    <h1>🧵 Threadworks • Embroidery Production Calculator</h1>
    <p>Wilcom PDF files upload karein aur foran <strong>Dhaaga (Cones), Machine ka Waqt, aur Kharcha</strong> maloom karein.</p>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# STEP 1: UPLOAD OR LOAD SAMPLE
# ═══════════════════════════════════════════════════════════════════════════
c_up1, c_up2, c_up3 = st.columns([5, 2, 1.2])

with c_up1:
    uploads = st.file_uploader(
        "PDF Worksheets yahan drop karein (Front, Bazzo, Kali, Patti)",
        type=["pdf"],
        accept_multiple_files=True,
        key=f"up_{st.session_state.uploader_key}",
        help="Aap ek sath tamam parts ke Wilcom PDFs upload kar sakte hain"
    )

with c_up2:
    st.write("")
    st.write("")
    if st.button("📂 Sample Files Load Karein", use_container_width=True, help="Folder mein mojood 5 sample PDF parts load karein"):
        sample_files = sorted(glob.glob("*.pdf"))
        for s in sample_files:
            fname = os.path.basename(s)
            with open(s, "rb") as f:
                c = f.read()
                h = hashlib.sha256(c).hexdigest()
                try:
                    data = parse_wilcom_pdf(c, fname)
                    data["hash"] = h
                    st.session_state.parts[h] = data
                except Exception as e:
                    st.error(f"Error in {fname}: {e}")
        st.toast("5 Sample Parts Load ho gaye!", icon="✅")
        st.rerun()

with c_up3:
    st.write("")
    st.write("")
    if st.button("🗑️ Saaf Karein", use_container_width=True):
        st.session_state.parts = {}
        st.session_state.uploader_key += 1
        st.rerun()

# Handle new uploads
if uploads:
    for u in uploads:
        c = u.getvalue()
        h = hashlib.sha256(c).hexdigest()
        if h not in st.session_state.parts:
            try:
                data = parse_wilcom_pdf(c, u.name)
                data["hash"] = h
                st.session_state.parts[h] = data
            except Exception as e:
                st.error(f"File {u.name} read nahi ho saki: {e}")

if not st.session_state.parts:
    st.info("💡 **Shuru karne ke liye:** Upar Wilcom PDF files drop karein ya **'📂 Sample Files Load Karein'** button dabayein.")
    st.stop()


# ═══════════════════════════════════════════════════════════════════════════
# STEP 2: SIMPLE ORDER INPUTS (SIRF 3 ZAROORI CHEEZEIN)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown('<div class="step-header"><span>⚙️</span> Order & Machine Details</div>', unsafe_allow_html=True)

col_s1, col_s2, col_s3, col_s4 = st.columns(4)

with col_s1:
    num_pieces = st.number_input(
        "📦 Kitne Suits Bananey Hain?",
        min_value=1,
        max_value=50000,
        value=100,
        step=10,
        help="Order ki total quantity"
    )

with col_s2:
    machine_heads = st.number_input(
        "🏭 Machine ke Heads",
        min_value=1,
        max_value=100,
        value=28,
        step=1,
        help="Ek baar mein machine kitne suits nikalti hai (default 28)"
    )

with col_s3:
    stitch_rate = st.number_input(
        "💰 Stitch Rate (per 1,000 stitches)",
        min_value=0.05,
        max_value=10.0,
        value=0.45,
        step=0.05,
        format="%.2f",
        help="1,000 stitches ka rate (PKR)"
    )

with col_s4:
    cone_price = st.number_input(
        "🧵 1 Cone ki Qimat (PKR)",
        min_value=50.0,
        max_value=2000.0,
        value=280.0,
        step=10.0,
        help="Dhaaga ke 1 cone ki qimat"
    )

# Optional Advanced Settings Dropdown
with st.expander("⚙️ Mazeed Settings (Wastage %, RPM, Cones Capacity - Default theek hai agar samajh na aaye)"):
    col_a1, col_a2, col_a3, col_a4 = st.columns(4)
    with col_a1:
        meters_per_cone = st.number_input("1 Cone mein Meters", min_value=500.0, value=2770.0, step=100.0)
    with col_a2:
        waste_pct = st.number_input("Dhaaga Wastage (%)", min_value=0.0, max_value=25.0, value=10.0, step=1.0)
    with col_a3:
        machine_rpm = st.number_input("Machine Speed (RPM)", min_value=300, max_value=1100, value=750, step=25)
    with col_a4:
        shift_hours = st.selectbox("Shift ke Ghantay", [8.0, 10.0, 12.0], index=0)
    
    col_chk1, col_chk2 = st.columns(2)
    with col_chk1:
        include_same = st.checkbox("Matching Ground Thread ('same') Shamil Karein", value=True, help="Fabric matching base thread. Isay hamesha on rakhein.")
    with col_chk2:
        include_boring = st.checkbox("Boring Tool Thread Shamil Karein", value=False, help="Borer puncture tool; aam tor par colored thread consume nahi karta.")


# ═══════════════════════════════════════════════════════════════════════════
# STEP 3: SUIT KE PARTS & REPEAT CHECK
# ═══════════════════════════════════════════════════════════════════════════
st.markdown('<div class="step-header"><span>🧩</span> Suit ke Parts & Repeats (Check karein)</div>', unsafe_allow_html=True)
st.caption("Auto-detect ho chuka hai (maslan Bazzo = 1x ya 2x, Kali = 1x). Agar kisi part ki quantity badalni ho to 'Repeat (×)' mein tabdeel karein:")

part_rows = []
for h, p in st.session_state.parts.items():
    part_rows.append({
        "Hash": h,
        "Part Name": p["design_name"],
        "Base Stitches": p["stitches"],
        "Sequins": p["sequins_total"],
        "Size": f"{p['width_mm']:.0f} × {p['height_mm']:.0f} mm",
        "Repeat": float(p["repeat"]),
    })

df_parts_view = pd.DataFrame(part_rows)

edited_parts = st.data_editor(
    df_parts_view,
    key="simple_parts_editor",
    hide_index=True,
    use_container_width=True,
    disabled=["Hash", "Part Name", "Base Stitches", "Sequins", "Size"],
    column_config={
        "Hash": None,
        "Part Name": st.column_config.TextColumn("Suit ka Part", width="large"),
        "Base Stitches": st.column_config.NumberColumn("Stitches", format="%d"),
        "Sequins": st.column_config.NumberColumn("Sequins", format="%d"),
        "Size": st.column_config.TextColumn("Size (W × H)", width="small"),
        "Repeat": st.column_config.NumberColumn(
            "Suit mein Kitni Dafa? (Repeat ×)",
            min_value=0.1,
            max_value=20.0,
            step=0.5,
            format="%.1f",
            help="1 suit mein yeh part kitni dafa banega"
        )
    }
)

# Apply updated repeats
for _, r in edited_parts.iterrows():
    h = r["Hash"]
    st.session_state.parts[h]["repeat"] = float(r["Repeat"])


# ═══════════════════════════════════════════════════════════════════════════
# TOTALS CALCULATION
# ═══════════════════════════════════════════════════════════════════════════
total_suit_stitches = 0
total_suit_sequins = 0
total_suit_bobbin_m = 0.0
total_suit_thread_m = 0.0
colors_summary = {}

for h, p in st.session_state.parts.items():
    rep = p["repeat"]
    total_suit_stitches += int(round(p["stitches"] * rep))
    total_suit_sequins += int(round(p["sequins_total"] * rep))
    total_suit_bobbin_m += p["total_bobbin_m"] * rep

    for tc in p["thread_colors"]:
        code = tc["code"]
        c_name = tc["name"]
        is_same = code.lower() == "same" or c_name.lower() == "same"
        is_boring = code.lower() == "boring" or c_name.lower() == "boring"

        if is_boring and not include_boring:
            continue
        if is_same and not include_same:
            continue

        c_key = code
        display_name = "Base Matching Thread (same)" if is_same else c_name

        if c_key not in colors_summary:
            colors_summary[c_key] = {
                "code": code,
                "name": display_name,
                "length_per_suit": 0.0,
            }
        colors_summary[c_key]["length_per_suit"] += tc["length_m"] * rep
        total_suit_thread_m += tc["length_m"] * rep

# Grand Totals
grand_stitches = total_suit_stitches * num_pieces
grand_sequins = total_suit_sequins * num_pieces

# Machine Timing
total_runs = math.ceil(num_pieces / machine_heads)
eff_spm = machine_rpm * 0.80  # 80% realistic factory efficiency
minutes_per_batch = (total_suit_stitches / eff_spm) if eff_spm > 0 else 0
hours_per_batch = minutes_per_batch / 60.0
total_hours = hours_per_batch * total_runs
shifts_needed = round(total_hours / shift_hours, 1) if shift_hours > 0 else 0
days_needed = round(shifts_needed / 2.0, 1)  # Assuming 2 shifts/day

# Cones Calculation
total_upper_cones = 0
cone_rows = []
for code, info in colors_summary.items():
    per_suit = info["length_per_suit"]
    total_m = per_suit * num_pieces
    with_waste_m = total_m * (1 + waste_pct / 100)
    cones = math.ceil(with_waste_m / meters_per_cone)
    if cones < 1:
        cones = 1
    total_upper_cones += cones

    cone_rows.append({
        "Color Code": str(code),
        "Color / Description": info["name"],
        "Per Suit (m)": round(per_suit, 1),
        "Order Meters": round(with_waste_m, 0),
        "Cones (🧵)": cones
    })

# Costing
stitching_cost = (total_suit_stitches / 1000.0) * stitch_rate
thread_cost = (total_upper_cones * cone_price) / num_pieces if num_pieces > 0 else 0
bobbin_cost_suit = (total_suit_bobbin_m * 1.1 / 10000.0) * 320.0
cost_per_suit = stitching_cost + thread_cost + bobbin_cost_suit
total_order_cost = cost_per_suit * num_pieces


# ═══════════════════════════════════════════════════════════════════════════
# STEP 4: BIG ASAN RESULTS (3 MAIN ANSWERS)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown('<div class="step-header"><span>🎯</span> Asaan Nateeja (Summary)</div>', unsafe_allow_html=True)

col_r1, col_r2, col_r3 = st.columns(3)

with col_r1:
    st.markdown(f"""
    <div class="result-card">
        <div class="result-label">🧵 Kul Dhaaga (Cones)</div>
        <div class="result-value">{total_upper_cones} Cones</div>
        <div class="result-sub">{len(colors_summary)} Colors | {waste_pct:.0f}% waste shamil hai</div>
    </div>
    """, unsafe_allow_html=True)

with col_r2:
    st.markdown(f"""
    <div class="result-card">
        <div class="result-label">⏱️ Machine ka Waqt</div>
        <div class="result-value">{shifts_needed} Shifts</div>
        <div class="result-sub">{total_runs} Machine Runs (~{days_needed} Din @ 2 shifts)</div>
    </div>
    """, unsafe_allow_html=True)

with col_r3:
    st.markdown(f"""
    <div class="result-card">
        <div class="result-label">💰 1 Suit ka Kharcha</div>
        <div class="result-value">₨ {cost_per_suit:,.0f}</div>
        <div class="result-sub">Total Order Kharcha: ₨ {total_order_cost:,.0f}</div>
    </div>
    """, unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════
# STEP 5: DETAILED SIMPLE TABS (SIRF 3 ASAN TABS)
# ═══════════════════════════════════════════════════════════════════════════
st.markdown("<br>", unsafe_allow_html=True)
tab_cones, tab_cost, tab_slip = st.tabs([
    "🧵 1. Dhaaga / Cones List (Store Requisition)",
    "💰 2. Kharcha Breakdown (Costing)",
    "📋 3. Machine Master Slip (Print / Copy)"
])


# ───────────────────────────────────────────────────────────────────────────
# TAB 1: CONES LIST
# ───────────────────────────────────────────────────────────────────────────
with tab_cones:
    st.markdown("#### 🧵 Store se nikalnay walay Dhaagay (Cones)")
    st.caption(f"{num_pieces} Suits ke liye har color ke kitne cones chahiye:")

    if cone_rows:
        df_cones = pd.DataFrame(cone_rows).sort_values("Cones (🧵)", ascending=False)
        st.dataframe(
            df_cones,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Color Code": st.column_config.TextColumn("Color Code", width="small"),
                "Color / Description": st.column_config.TextColumn("Dhaaga / Color Name", width="large"),
                "Per Suit (m)": st.column_config.NumberColumn("1 Suit mein (m)", format="%.1f m"),
                "Order Meters": st.column_config.NumberColumn(f"Total Meters ({num_pieces} suits)", format="%,d m"),
                "Cones (🧵)": st.column_config.NumberColumn("Kul Cones", format="%d Cones 🧵"),
            }
        )

        col_d_csv, col_d_clip = st.columns([1, 1])
        with col_d_csv:
            st.download_button(
                "📥 Dhaaga List CSV Download Karein",
                df_cones.to_csv(index=False).encode("utf-8-sig"),
                f"Dhaga_List_{num_pieces}_Suits.csv",
                "text/csv",
                use_container_width=True
            )
        with col_d_clip:
            whatsapp_text = f"🧵 *DHAAGA REQUISITION ({num_pieces} Suits)*\n"
            for _, r in df_cones.iterrows():
                whatsapp_text += f"- Code {r['Color Code']} ({r['Color / Description']}): *{r['Cones (🧵)']} Cones*\n"
            whatsapp_text += f"\n*Kul Cones:* {total_upper_cones}\n*Machine Runs:* {total_runs}"
            st.download_button(
                "📋 WhatsApp / Note File (.txt)",
                whatsapp_text,
                f"Dhaga_WhatsApp_{num_pieces}_suits.txt",
                "text/plain",
                use_container_width=True
            )


# ───────────────────────────────────────────────────────────────────────────
# TAB 2: COSTING BREAKDOWN
# ───────────────────────────────────────────────────────────────────────────
with tab_cost:
    st.markdown("#### 💰 1 Suit aur Total Order ka Kharcha")
    
    col_c1, col_c2 = st.columns(2)

    with col_c1:
        st.markdown(f"""
        <div style="background:var(--secondary-background-color); border:1px solid rgba(128,128,128,0.2); border-radius:12px; padding:18px;">
            <h4 style="margin-top:0; color:#0f766e;">1 Suit ka Kharcha:</h4>
            <table style="width:100%; border-collapse:collapse; font-size:0.95rem;">
                <tr style="border-bottom:1px solid rgba(128,128,128,0.2);">
                    <td style="padding:8px 0;">Stitching Kharcha ({total_suit_stitches:,} st @ {stitch_rate}/1k):</td>
                    <td style="text-align:right; font-weight:700;">₨ {stitching_cost:,.2f}</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(128,128,128,0.2);">
                    <td style="padding:8px 0;">Dhaaga / Cones Kharcha:</td>
                    <td style="text-align:right; font-weight:700;">₨ {thread_cost:,.2f}</td>
                </tr>
                <tr style="border-bottom:1px solid rgba(128,128,128,0.2);">
                    <td style="padding:8px 0;">Bobbin Bottom Thread:</td>
                    <td style="text-align:right; font-weight:700;">₨ {bobbin_cost_suit:,.2f}</td>
                </tr>
                <tr style="font-size:1.15rem; font-weight:800; color:#0f766e; border-top:2px solid #0d9488;">
                    <td style="padding:12px 0;">Kul Kharcha (Cost / Suit):</td>
                    <td style="text-align:right;">₨ {cost_per_suit:,.0f}</td>
                </tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    with col_c2:
        profit_pct = st.slider("Apna Munafa / Profit Margin (%)", min_value=0, max_value=60, value=25, step=5)
        profit_val = cost_per_suit * (profit_pct / 100.0)
        sale_price = cost_per_suit + profit_val

        st.markdown(f"""
        <div style="background:rgba(13,148,136,0.06); border:2px dashed #0d9488; border-radius:12px; padding:18px;">
            <h4 style="margin-top:0; color:#0f766e;">Client ke liye Qimat (Quotation):</h4>
            <p>1 Suit ki Cost: <strong>₨ {cost_per_suit:,.0f}</strong></p>
            <p>Munafa ({profit_pct}%): <strong style="color:#0d9488;">+ ₨ {profit_val:,.0f}</strong></p>
            <hr style="border-color:rgba(13,148,136,0.3);">
            <div style="font-size:1.3rem; font-weight:800; color:#094840;">
                Bechnay ki Qimat: <span style="color:#0d9488;">₨ {sale_price:,.0f} / Suit</span>
            </div>
            <p style="font-size:0.85rem; color:gray; margin-top:8px;">
                Total Order Bill ({num_pieces} Suits): <strong>₨ {sale_price * num_pieces:,.0f}</strong>
                <br>Kul Munafa: <strong style="color:#10b981;">₨ {profit_val * num_pieces:,.0f}</strong>
            </p>
        </div>
        """, unsafe_allow_html=True)


# ───────────────────────────────────────────────────────────────────────────
# TAB 3: MACHINE MASTER SLIP
# ───────────────────────────────────────────────────────────────────────────
with tab_slip:
    st.markdown("#### 📋 Machine Master & Store Slip")
    st.caption("Yeh slip copy ya print karke machine master aur storekeeper ko de sakte hain:")

    slip_text = f"""------------------------------------------------------------
              EMBROIDERY JOB SLIP
------------------------------------------------------------
Order: {num_pieces} Suits | Machine Heads: {machine_heads}
Total Stitches per Suit: {total_suit_stitches:,}
Grand Stitches: {grand_stitches:,}
Machine Runs / Batches: {total_runs} Runs
Andazan Waqt: {shifts_needed} Shifts (~{days_needed} Din)
------------------------------------------------------------
SUIT KE PARTS (CUT-SHEET):
"""
    for h, p in st.session_state.parts.items():
        slip_text += f"- {p['design_name']:<35} : Repeat {p['repeat']}x ({p['stitches']:,} st)\n"

    slip_text += f"""------------------------------------------------------------
DHAAGA REQUISITION (STORE KE LIYE):
"""
    for code, info in colors_summary.items():
        w_m = info["length_per_suit"] * num_pieces * (1 + waste_pct / 100)
        c_req = math.ceil(w_m / meters_per_cone)
        if c_req < 1: c_req = 1
        slip_text += f"• Code {str(code):<10} {info['name'][:20]:<20} : {c_req:>2} Cones ({w_m:>6,.0f}m)\n"

    slip_text += f"""------------------------------------------------------------
KUL CONES: {total_upper_cones} Cones
------------------------------------------------------------
Master Signature: _______________   Store Issue: ___________
"""

    st.text_area("Slip Text", slip_text, height=360)

    st.download_button(
        "📥 Slip Download Karein (.txt)",
        slip_text,
        f"Master_Slip_{num_pieces}_suits.txt",
        "text/plain",
        use_container_width=True
    )
