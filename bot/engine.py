"""
Threadworks WhatsApp Bot Engine.
Processes incoming Wilcom PDF files & Text Commands, generates production calculations,
formatted WhatsApp messages and printable PDF Job Cards.
"""

import re
import math
import pandas as pd
from core.parser import parse_wilcom_pdf, extract_repeat_from_text
from core.calculator import (
    aggregate_suit_parts,
    calculate_full_production,
    compute_part_heads_config,
    DEFAULT_CONE_PRICE,
    DEFAULT_MACHINE_RPM,
    DEFAULT_SHIFT_HOURS
)
from core.pdf_report import generate_job_card_pdf
from bot.config import (
    BOT_DEFAULT_HEADS,
    BOT_DEFAULT_SHADES,
    BOT_DEFAULT_LOTS,
    BOT_DEFAULT_RATE,
    BOT_DEFAULT_WASTE,
    BOT_DEFAULT_CONE_CAPACITY
)


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


def process_whatsapp_pdf(pdf_bytes: bytes, filename: str, overrides: dict = None) -> dict:
    """
    Core entrypoint for WhatsApp document processing.
    Parses PDF, computes complete industrial production metrics, and builds text + PDF responses.
    """
    if overrides is None:
        overrides = {}

    # 1. Determine heads (Auto-detect from filename if present, else user override or default)
    heads_val = overrides.get("heads")
    if not heads_val:
        h_match = re.search(r'\b(20|24|28|30|32|36|40|44|48|56)\s*(?:head|heads|h)\b', filename, re.I)
        if h_match:
            heads_val = int(h_match.group(1))
        else:
            heads_val = BOT_DEFAULT_HEADS

    base_shades_val = int(overrides.get("shades", BOT_DEFAULT_SHADES))
    lots_val = float(overrides.get("lots", BOT_DEFAULT_LOTS))
    rate_val = float(overrides.get("rate", BOT_DEFAULT_RATE))
    waste_val = float(overrides.get("waste", BOT_DEFAULT_WASTE))
    cone_cap_val = float(overrides.get("cone_cap", BOT_DEFAULT_CONE_CAPACITY))

    pieces_per_lot = heads_val * base_shades_val
    num_pieces = int(round(pieces_per_lot * lots_val))

    # 2. Parse Wilcom PDF
    parsed_parts = parse_wilcom_pdf(pdf_bytes, filename)
    if isinstance(parsed_parts, dict):
        parsed_parts = [parsed_parts]

    parts_dict = {}
    for idx, p in enumerate(parsed_parts):
        sub_h = f"part_{idx}"
        # Auto-compute head mode & repeat
        target_str = f"{p.get('design_name', '')} {filename}"
        auto_rep = extract_repeat_from_text(target_str)
        cur_cfg = compute_part_heads_config(
            target_str,
            auto_rep,
            heads_val,
            base_shades_val,
            p
        )
        p["mode"] = cur_cfg["mode"]
        p["repeat"] = cur_cfg["repeat"]
        p["heads"] = cur_cfg["heads"]
        parts_dict[sub_h] = p

    # 3. Aggregate suit parts
    total_suit_stitches, total_suit_sequins, total_suit_bobbin_m, colors_dict = aggregate_suit_parts(
        parts_dict,
        include_boring=False,
        default_heads=heads_val,
        base_colors=base_shades_val
    )

    # 4. Run calculation engine
    results = calculate_full_production(
        total_suit_stitches=total_suit_stitches,
        total_suit_bobbin_m=total_suit_bobbin_m,
        colors_dict=colors_dict,
        machine_heads=heads_val,
        base_colors_count=base_shades_val,
        num_pieces=num_pieces,
        lots_count=lots_val,
        cone_capacity_val=cone_cap_val,
        cone_unit="Meters",
        waste_pct=waste_val,
        stitch_rate=rate_val,
        cone_price=DEFAULT_CONE_PRICE,
        machine_rpm=DEFAULT_MACHINE_RPM,
        shift_hours=DEFAULT_SHIFT_HOURS,
        parts=parts_dict
    )

    # 5. Extract results
    cone_rows = results["cone_rows"]
    df_cones = pd.DataFrame(cone_rows).sort_values("Kul Cones (🧵)", ascending=False) if cone_rows else pd.DataFrame()
    total_order_cones = results["total_order_cones"]
    piece_rate = results["piece_rate"]
    total_order_amount = results["total_order_amount"]
    total_runs = results["total_runs"]
    part_runs = results.get("part_runs_details", {})

    frame_length_m = results.get("frame_length_m", 0.0)
    total_bukram_m = results.get("total_bukram_m", 0.0)
    bukram_rolls_int = results.get("bukram_rolls_int", 0)

    bobbin_grams = results.get("bobbin_grams", 0.0)
    bobbin_kg = results.get("bobbin_kg", 0.0)
    bobbin_cones = results.get("bobbin_cones", 0)
    total_order_bobbin_m = results.get("order_bobbin_m", 0.0)

    real_total_hours = results.get("real_total_hours", 0.0)
    real_shifts = results.get("real_shifts", 1)
    real_days = results.get("real_days", 1.0)

    net_profit_per_suit = results.get("net_profit_per_suit", 0.0)
    total_order_profit = results.get("total_order_profit", 0.0)

    # 6. Format Design Name
    first_p = next(iter(parts_dict.values())) if parts_dict else {}
    raw_dn = first_p.get("design_name") or filename.rsplit(".", 1)[0]
    clean_dn = re.sub(r'[\(\[\{].*?[\)\]\}]', '', raw_dn).strip() or raw_dn.strip()
    safe_prefix = re.sub(r'[\\/*?:"<>|\s]', '_', clean_dn).strip('_') or "Design"

    # 7. Generate Printable A4 PDF Job Card
    pdf_parts_list = []
    for h, p in parts_dict.items():
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
    if not df_cones.empty:
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
        "color": "White",
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
        design_name=clean_dn,
        num_pieces=num_pieces,
        lots_count=lots_val,
        machine_heads=heads_val,
        base_colors_count=base_shades_val,
        suits_per_base_color=round(num_pieces / max(1, base_shades_val)),
        total_suit_stitches=total_suit_stitches,
        stitch_rate=rate_val,
        piece_rate=piece_rate,
        total_order_amount=total_order_amount,
        cone_capacity_val=cone_cap_val,
        cone_unit="Meters",
        waste_pct=waste_val,
        shifts_needed=real_shifts,
        days_needed=real_days,
        total_runs=total_runs,
        parts_data=pdf_parts_list,
        cones_data=pdf_cones_list,
        total_order_cones=total_order_cones,
        bobbin_data=bobbin_dict,
        bukram_data=bukram_dict
    )

    # 8. Build WhatsApp Formatted Message
    msg = f"🧵 *THREADWORKS • EMBROIDERY BOT*\n"
    msg += f"📋 *Design:* {clean_dn}\n"
    msg += f"📦 *Order:* *{num_pieces} Suits* ({lots_val:g} Lot) | *{heads_val} Heads* | *{base_shades_val} Shades*\n"
    msg += f"─────────────────────────\n"
    msg += f"⚡ *Kul Stitches:* *{total_suit_stitches:,} st*\n"
    msg += f"💵 *1 Suit Rate:* *Rs {piece_rate:,.2f}* (@ Rs {rate_val:.2f}/1k)\n"
    msg += f"💰 *Poori Lot Bill:* *Rs {total_order_amount:,.0f}*\n"
    msg += f"─────────────────────────\n"
    msg += f"🧵 *STORE REQUISITION (DHAAGA & MATERIAL):*\n"
    if not df_cones.empty:
        for _, r in df_cones.iterrows():
            msg += f"{format_whatsapp_row(r)}\n"
    if bobbin_cones > 0:
        msg += f"• *Bobbin/Khicha (White):* *{bobbin_cones} Cones* (~{bobbin_kg:.2f} kg)\n"
    if bukram_rolls_int > 0:
        msg += f"• *Bukram/Paper:* *{bukram_rolls_int} Rolls* (~{total_bukram_m:,.0f}m / Frame: {frame_length_m:.1f}m)\n"
    msg += f"🔄 *Machine Repeats:* *{total_runs} Repeat*\n"
    msg += f"─────────────────────────\n"
    msg += f"⏱️ *FLOOR TIMING:* ~*{real_shifts} Shifts* (~{real_days} Din @ 680 SPM)\n"
    msg += f"🌟 *SAAF MUNAFA (PROFIT):* *Rs {net_profit_per_suit:,.2f}* / Suit (Lot: *Rs {total_order_profit:,.0f}*)\n"
    msg += f"─────────────────────────\n"
    msg += f"🖨️ *Printable A4 Job Card PDF neechay attach hai.*"

    return {
        "design_name": clean_dn,
        "text_reply": msg,
        "pdf_bytes": job_card_pdf_bytes,
        "pdf_filename": f"{safe_prefix}_Job_Card_{num_pieces}_suits.pdf",
        "metrics": {
            "total_suit_stitches": total_suit_stitches,
            "piece_rate": piece_rate,
            "total_order_amount": total_order_amount,
            "total_order_cones": total_order_cones,
            "bobbin_cones": bobbin_cones,
            "bukram_rolls": bukram_rolls_int,
            "real_shifts": real_shifts,
            "net_profit_suit": net_profit_per_suit,
            "total_profit": total_order_profit
        }
    }


def process_whatsapp_text_command(cmd_text: str, session: dict) -> str:
    """
    Handles user text commands on WhatsApp (e.g. heads 28, rate 1.25, status, help).
    """
    text = cmd_text.strip().lower()

    if text in ("help", "salam", "hi", "hello", "start", "?", "madad"):
        return (
            "🧵 *THREADWORKS WHATSAPP BOT*\n\n"
            "👋 Assalam-o-Alaikum!\n"
            "Mujhy kisi bhi design ki **Wilcom PDF** bhejein, main 3 second mein:\n"
            "• 🧵 Kul Dhaaga & Cones List\n"
            "• 💵 1 Suit Rate & Poori Lot ka Bill\n"
            "• 📜 Bukram Rolls & Bobbin (Khicha) kg\n"
            "• 🖨️ Tayyar Printable PDF Job Card\n"
            "bana kar bhej doon ga!\n\n"
            "⚙️ *Settings Badalny k Commands:*\n"
            "• `heads 28` ➔ Machine heads badalna\n"
            "• `rate 1.25` ➔ Stitch rate badalna\n"
            "• `lots 2` ➔ Order lots badalna\n"
            "• `shades 4` ➔ Base cloth colors badalna\n"
            "• `status` ➔ Mojooda settings dekhna"
        )

    if text.startswith("head"):
        m = re.search(r'\d+', text)
        if m:
            val = int(m.group(0))
            session["heads"] = val
            return f"✅ Machine Heads set kar diye gaye: *{val} Heads*"
        return "⚠️ Heads number likhein, misal k taur par: `heads 28`"

    if text.startswith("rate"):
        m = re.search(r'[\d\.]+', text)
        if m:
            val = float(m.group(0))
            session["rate"] = val
            return f"✅ Stitch Rate set kar diya gaya: *Rs {val:.2f}* / 1,000 stitches"
        return "⚠️ Rate number likhein, misal k taur par: `rate 1.20`"

    if text.startswith("lot"):
        m = re.search(r'[\d\.]+', text)
        if m:
            val = float(m.group(0))
            session["lots"] = val
            return f"✅ Order Lots set kar di gayin: *{val:g} Lots*"
        return "⚠️ Lots number likhein, misal k taur par: `lots 2`"

    if text.startswith("shade") or text.startswith("color"):
        m = re.search(r'\d+', text)
        if m:
            val = int(m.group(0))
            session["shades"] = val
            return f"✅ Base Shades set kar diye gaye: *{val} Shades*"
        return "⚠️ Shades number likhein, misal k taur par: `shades 4`"

    if text in ("status", "setting", "settings"):
        h = session.get("heads", BOT_DEFAULT_HEADS)
        s = session.get("shades", BOT_DEFAULT_SHADES)
        l = session.get("lots", BOT_DEFAULT_LOTS)
        r = session.get("rate", BOT_DEFAULT_RATE)
        return (
            "⚙️ *MOJOODA BOT SETTINGS:*\n"
            f"• Machine Heads: *{h} Heads*\n"
            f"• Base Shades: *{s} Colors*\n"
            f"• Kul Lots: *{l:g} Lot* ({h * s * l:,.0f} Suits)\n"
            f"• Stitch Rate: *Rs {r:.2f}* / 1k stitches\n\n"
            "Ab apni Wilcom PDF bhejein!"
        )

    return (
        "💡 Samajh nahi aaya. Apni **Wilcom PDF** bhejein ya `help` likh kar commands dekhein."
    )

