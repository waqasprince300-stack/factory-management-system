"""
Production Calculation Engine for Embroidery Operations.
Implements Separate Systems for:
1. Dhaaga (Thread / Cones) Calculation
2. Stitch / 1 Piece Rate Calculation (per 1,000 stitches)

Supports:
- 1 Repeat (Saray Head vs Half Head)
- Half Repeat (0.5 R - Saray Head vs Half Head)
- 9 Head (3 Colors / Frame)
- 4 Head (Base Colors / Frame, e.g. 6 Colors)
- Custom Repeat and Head configurations
- Matching (Tone-on-Tone / Same) vs Common Thread Cones Requisition
"""

import math
import re
from core.config import (
    YARDS_TO_METERS,
    METERS_TO_YARDS,
    DEFAULT_EFFICIENCY,
    DEFAULT_BOBBIN_RATE_PER_METER,
    DEFAULT_MACHINE_HEADS,
    DEFAULT_CONE_PRICE,
    DEFAULT_MACHINE_RPM,
    DEFAULT_SHIFT_HOURS,
    DOUBLE_HEAD_WIDTH_THRESHOLD_MM
)


def is_same_color(code: str, name: str) -> bool:
    """
    Identifies if a thread color is tone-on-tone / base matching.
    Matches: 'same', 'same up', 'same lite', 'same light', 'same dark', 'matching', 'base', 'tone'.
    """
    text = f"{code} {name}".lower()
    pattern = r'\b(same|same\s*up|same\s*lite|same\s*light|same\s*dark|same\s*\d+|matching|base\s*match|tone)\b'
    return bool(re.search(pattern, text, re.I))


def is_boring_tool(code: str, name: str) -> bool:
    """
    Detects Wilcom boring punch tool rows.
    """
    text = f"{code} {name}".lower()
    return bool(re.search(r'\bboring\b', text, re.I))


def get_part_mode_options(machine_heads: int, base_colors: int = 6) -> dict:
    """
    Returns user-friendly labels for all supported repeat and head modes in Roman Urdu.
    """
    def_h = max(1, machine_heads)
    half_h = max(1, def_h // 2)
    quarter_h = max(1, def_h // 4)
    b_col = max(1, base_colors)
    h_4 = max(1, round(def_h / b_col))
    h_9 = max(1, round(def_h / 3))

    return {
        "1_rep_all": f"Saray Head ({def_h} Heads)",
        "1_rep_half": f"Half Head / Double Head ({half_h} Heads)",
        "half_rep_all": f"Half Repeat — 2 Colors Saray Head ({half_h}H har color)",
        "half_rep_half": f"Half Repeat — 2 Colors Half Head ({quarter_h}H har color)",
        "head_9": f"9 Head — 3 Colors / Frame ({h_9} Heads har color)",
        "head_4": f"4 Head — {b_col} Colors / Frame ({h_4} Heads har color)",
        "custom": "Custom (Apni Marzi k Heads)"
    }


def compute_part_heads_config(
    target_name: str,
    repeat: float = 1.0,
    machine_heads: int = DEFAULT_MACHINE_HEADS,
    base_colors: int = 6,
    part_dict: dict = None
) -> dict:
    """
    Calculates active heads, thread heads, and stitch rate multipliers based on factory rules:

    1. 1 Repeat (Saray Head - 28H):
       - Rate: 1x stitches added to 1 piece
       - Dhaaga: 28 heads thread

    2. 1 Repeat (Half Head / Double Head - 14H):
       - Trigger: Width > 400 mm, ya '14H', 'double head', 'half head'
       - Rate: 1x stitches added to 1 piece (stich 1 bar hi add karo)
       - Dhaaga: 14 heads thread

    3. Half Repeat — 2 Colors Saray Head (14H har color on 28H):
       - 2 colors mil kar 1 repeat complete kartay hain (28 heads par)
       - Har color par 14 heads chaltay hain
       - Rate: 0.5x stitches added to 1 piece
       - Dhaaga: 14 heads thread per color

    4. Half Repeat — 2 Colors Half Head (7H har color on 28H):
       - 2 colors mil kar 1 repeat complete kartay hain (Alternate 14 heads par)
       - Har color par 14 / 2 = 7 heads chaltay hain
       - Rate: 0.5x stitches added to 1 piece
       - Dhaaga: 7 heads thread per color

    5. 9 Head (3 Colors / Frame):
       - 3 colors mil kar 1 repeat complete kartay hain
       - Dhaaga: Total machine heads / 3 (e.g. 28 / 3 = 9.33 heads thread)
       - Rate: (Stitches * Rate / 1000 * Machine_Heads) / Total_Pieces = Stitches / 3

    6. 4 Head (Base Colors, e.g. 6 Colors / Frame):
       - 6 colors mil kar 1 repeat complete kartay hain
       - Dhaaga: Total machine heads / Base_Colors (e.g. 28 / 6 = 4.67 heads thread)
       - Rate: (Stitches * Rate / 1000 * Machine_Heads) / Total_Pieces = Stitches / Base_Colors
    """
    target = str(target_name or "")
    part_d = part_dict or {}
    def_h = max(1, machine_heads)
    b_col = max(1, base_colors)
    half_h = max(1, def_h // 2)
    quarter_h = max(1, def_h // 4)

    mode = part_d.get("mode")
    if not mode or not part_d.get("_manual_mode"):
        head_m = re.search(r'[\[\(\{]\s*(\d+)\s*(?:h|head|heads)\b', target, re.I) or re.search(r'\b(\d+)\s*(?:h|head|heads)\b', target, re.I)
        detected_heads = int(head_m.group(1)) if head_m else None

        is_quarter = bool(re.search(r'\b(quarter|4\s*time|7\s*h)\b', target, re.I))
        is_half_rep = (abs(repeat - 0.5) < 0.05) or (
            repeat < 0.9 and bool(re.search(r'(?<!\d)(?<!\+)\bhalf\b', target, re.I))
        )
        is_half_head = bool(re.search(r'\b(14\s*h|14\s*head|15\s*h|15\s*head|half\s*head|half\s*heads|double\s*head)\b', target, re.I))

        # Factory Double Head Rule: If Width > 450 mm, physical head distance requires alternate heads (Half Head)
        width_val = float(part_d.get("width_mm") or 0.0)
        is_double_head_by_width = (width_val > DOUBLE_HEAD_WIDTH_THRESHOLD_MM)

        is_two_color_frame = bool(re.search(r'\b(2\s*clr|2\s*color|2\s*shade)\b', target, re.I))

        if detected_heads == 4 or bool(re.search(r'\b4\s*h(?:ead)?\b', target, re.I)):
            mode = "head_4"
        elif detected_heads == 9 or bool(re.search(r'\b9\s*h(?:ead)?\b', target, re.I)):
            mode = "head_9"
        elif is_two_color_frame and (is_quarter or (part_d.get("heads") and int(part_d["heads"]) <= quarter_h)):
            mode = "half_rep_half"
        elif is_two_color_frame:
            mode = "half_rep_all"
        elif is_half_head or is_double_head_by_width or (part_d.get("heads") and int(part_d["heads"]) <= half_h):
            mode = "1_rep_half"
        else:
            mode = "1_rep_all"

    rep = float(part_d.get("repeat", repeat if repeat and repeat > 0 else 1.0))

    if mode == "1_rep_all":
        h = def_h
        thread_h = float(def_h)
        rate_mult = rep * 1.0
        badge = f"{rep:g}R · Saray Head ({def_h}H)"
        badge_type = "standard"
        desc = f"{rep:g} Repeat — Saray {def_h} Heads (Stitches × {rep:g})"
        colors_in_rep = 1

    elif mode == "1_rep_half":
        h = half_h
        thread_h = float(half_h)
        rate_mult = rep * 1.0
        width_val = float(part_d.get("width_mm") or 0.0)
        if width_val > DOUBLE_HEAD_WIDTH_THRESHOLD_MM:
            badge = f"{rep:g}R · Double Head ({half_h}H)"
            desc = f"{rep:g} Repeat — Double Head ({half_h} Heads) [Width: {width_val:g}mm > 450mm -> Auto Half Head]"
        else:
            badge = f"{rep:g}R · Half Head ({half_h}H)"
            desc = f"{rep:g} Repeat — Half {half_h} Heads (Stitches × {rep:g})"
        badge_type = "double"
        colors_in_rep = 1

    elif mode == "half_rep_all":
        h = half_h
        thread_h = float(half_h)
        rate_mult = rep
        badge = f"{rep:g}R · 2 Clr Saray Head ({half_h}H)"
        badge_type = "standard"
        desc = f"Half Repeat ({rep:g}R) — 2 Colors mil kar 1 Repeat, Saray Head ({half_h}H har color)"
        colors_in_rep = 2

    elif mode in ("half_rep_half", "half_rep_quarter"):
        h = quarter_h
        thread_h = float(quarter_h)
        rate_mult = rep
        badge = f"{rep:g}R · 2 Clr Half Head ({quarter_h}H)"
        badge_type = "double"
        desc = f"Half Repeat ({rep:g}R) — 2 Colors mil kar 1 Repeat, Half Head ({quarter_h}H har color)"
        colors_in_rep = 2

    elif mode == "head_9":
        thread_h = def_h / 3.0
        h = max(1, round(thread_h))
        rate_mult = rep * (1.0 / 3.0)
        badge = f"{rep:g}R · 9H ({h}H/clr)"
        badge_type = "multi"
        desc = f"9 Head ({rep:g}R) — 3 Colors mil kar 1 Repeat (Stitches × {rep:g} ÷ 3)"
        colors_in_rep = 3

    elif mode == "head_4":
        thread_h = def_h / float(b_col)
        h = max(1, round(thread_h))
        rate_mult = rep * (1.0 / float(b_col))
        badge = f"{rep:g}R · 4H ({h}H/clr)"
        badge_type = "multi"
        desc = f"4 Head ({rep:g}R) — {b_col} Colors mil kar 1 Repeat (Stitches × {rep:g} ÷ {b_col})"
        colors_in_rep = b_col

    else:  # "custom"
        h = int(part_d.get("heads", def_h))
        thread_h = float(h)
        rate_mult = rep
        badge = f"Custom ({rep:g}R · {h}H)"
        badge_type = "standard"
        desc = f"Custom ({rep:g} Repeat · {h} Heads)"
        colors_in_rep = 1
    return {
        "mode": mode,
        "type": mode,
        "repeat": rep,
        "heads": h,
        "thread_heads": thread_h,
        "rate_st_mult": rate_mult,
        "suit_mult": rate_mult,
        "badge": badge,
        "badge_type": badge_type,
        "desc": desc,
        "colors": colors_in_rep,
        "colors_in_rep": colors_in_rep
    }


def aggregate_suit_parts(
    parts: dict,
    include_boring: bool = False,
    default_heads: int = DEFAULT_MACHINE_HEADS,
    base_colors: int = 6
) -> tuple[int, int, float, dict]:
    """
    Sums up 1 Suit's total stitches, sequins, bobbin, and thread consumption across all parts.
    Keeps Thread meters (Dhaaga) and Stitches / Rate strictly separate.
    """
    total_stitches = 0
    total_sequins = 0
    total_bobbin_m = 0.0
    colors_dict = {}

    def_h = max(1, default_heads)
    b_col = max(1, base_colors)

    for _, p in parts.items():
        rep = float(p.get("repeat", 1.0))
        cfg = compute_part_heads_config(
            f"{p.get('design_name', '')} {p.get('file_name', '')}",
            rep,
            def_h,
            b_col,
            p
        )

        p_st = int(round(p.get("stitches", 0)))
        p_seq = int(round(p.get("sequins_total", 0)))
        p_bob = float(p.get("total_bobbin_m", 0.0))

        suit_st = int(round(p_st * cfg["rate_st_mult"]))
        suit_seq = int(round(p_seq * cfg["rate_st_mult"]))
        suit_bob = p_bob * cfg["rate_st_mult"]

        total_stitches += suit_st
        total_sequins += suit_seq
        total_bobbin_m += suit_bob

        # Store calculated values back into part dict for instant UI display
        p["effective_suit_stitches"] = suit_st
        p["active_heads_calculated"] = cfg["heads"]
        p["thread_heads_calculated"] = cfg["thread_heads"]
        p["cfg"] = cfg

        for tc in p.get("thread_colors", []):
            raw_code = str(tc.get("code", "")).strip()
            raw_name = str(tc.get("name", "")).strip() or raw_code
            length_single = float(tc.get("length_m", 0.0))
            needle = int(tc.get("needle", 1))

            if is_boring_tool(raw_code, raw_name) and not include_boring:
                continue

            # Thread for 1 Suit and Thread for 1 Machine Frame
            part_suit_m = length_single * cfg["rate_st_mult"]
            part_frame_m = length_single * cfg["thread_heads"] * cfg["repeat"]

            # Normalized representations (trim spaces, uppercase for comparison)
            norm_code = re.sub(r'\s+', ' ', raw_code).strip()
            norm_name = re.sub(r'\s+', ' ', raw_name).strip() or norm_code
            code_upper = norm_code.upper()
            name_upper = norm_name.upper()

            # Find matching existing thread color:
            target_key = None
            for ex_k, ex_info in colors_dict.items():
                ex_code_upper = ex_info["code"].strip().upper()
                ex_name_upper = ex_info["name"].strip().upper()
                ex_needle = ex_info["needle"]

                if code_upper and code_upper not in ("-", "NONE", "N/A", "NULL") and code_upper == ex_code_upper:
                    target_key = ex_k
                    break

                if needle == ex_needle and name_upper == ex_name_upper:
                    target_key = ex_k
                    break

                if needle == ex_needle and (code_upper == ex_name_upper or name_upper == ex_code_upper):
                    target_key = ex_k
                    break

            if not target_key:
                target_key = code_upper if (code_upper and code_upper not in ("-", "NONE", "N/A")) else f"N{needle}_{name_upper}"
                display_code = norm_code.capitalize() if (norm_code.islower() and not norm_code.isdigit()) else norm_code
                display_name = norm_name if norm_name else display_code

                colors_dict[target_key] = {
                    "needle": needle,
                    "code": display_code,
                    "name": display_name,
                    "is_same": is_same_color(raw_code, raw_name),
                    "meters_1_suit": 0.0,
                    "meters_1_frame": 0.0,
                    "active_heads": cfg["heads"]
                }
            else:
                cur_code = colors_dict[target_key]["code"]
                if cur_code.islower() and not norm_code.islower():
                    colors_dict[target_key]["code"] = norm_code

                cur_name = colors_dict[target_key]["name"]
                if (not cur_name or cur_name.upper() == code_upper) and norm_name and norm_name.upper() != code_upper:
                    colors_dict[target_key]["name"] = norm_name

                if is_same_color(raw_code, raw_name):
                    colors_dict[target_key]["is_same"] = True

            colors_dict[target_key]["meters_1_suit"] += part_suit_m
            colors_dict[target_key]["meters_1_frame"] += part_frame_m
            colors_dict[target_key]["active_heads"] = max(
                colors_dict[target_key].get("active_heads", 0),
                cfg["heads"]
            )

    return total_stitches, total_sequins, total_bobbin_m, colors_dict


def calculate_full_production(
    total_suit_stitches: int,
    total_suit_bobbin_m: float,
    colors_dict: dict,
    machine_heads: int,
    base_colors_count: int,
    num_pieces: int,
    lots_count: float,
    cone_capacity_val: float,
    cone_unit: str,
    waste_pct: float,
    stitch_rate: float,
    cone_price: float = DEFAULT_CONE_PRICE,
    machine_rpm: int = DEFAULT_MACHINE_RPM,
    shift_hours: float = DEFAULT_SHIFT_HOURS,
    parts: dict = None
) -> dict:
    """
    Executes production, thread cones, and stitching cost calculations.
    """
    if "Yards" in cone_unit:
        cone_cap_m = cone_capacity_val * YARDS_TO_METERS
        cone_cap_yd = cone_capacity_val
    else:
        cone_cap_m = cone_capacity_val
        cone_cap_yd = cone_capacity_val * METERS_TO_YARDS

    waste_mult = 1.0 + (waste_pct / 100.0)

    # Suits per base color (e.g. 168 / 6 = 28 suits per color)
    b_count = max(1, base_colors_count)
    suits_per_base_color = max(1, int(round(num_pieces / b_count)))
    frames_per_base_color = round(suits_per_base_color / max(1, machine_heads), 1)

    cone_rows = []
    total_order_cones_int = 0
    total_order_cones_exact = 0.0
    total_common_cones_int = 0
    total_same_cones_int = 0

    for code, info in colors_dict.items():
        m_1_suit = info["meters_1_suit"]
        yd_1_suit = m_1_suit * METERS_TO_YARDS
        m_1_frame = info.get("meters_1_frame", m_1_suit * machine_heads)

        is_same = info.get("is_same", False)

        # Cones per single suit
        if "Yards" in cone_unit:
            cones_per_suit = yd_1_suit / cone_cap_yd if cone_cap_yd > 0 else 0
        else:
            cones_per_suit = m_1_suit / cone_cap_m if cone_cap_m > 0 else 0

        if is_same:
            # ─────────────────────────────────────────────────────────────
            # MATCHING / SAME DHAGA FORMULA:
            # Runs only on its base color suits (suits_per_base_color)!
            # ─────────────────────────────────────────────────────────────
            exact_cones_per_shade = cones_per_suit * suits_per_base_color * waste_mult
            int_cones_per_shade = math.ceil(exact_cones_per_shade) if exact_cones_per_shade > 0 else 1

            total_same_shade_cones = int_cones_per_shade * b_count
            total_same_cones_int += total_same_shade_cones
            total_order_cones_int += total_same_shade_cones
            total_order_cones_exact += (exact_cones_per_shade * b_count)

            formula_note = (
                f"{int_cones_per_shade} Cones har color ({suits_per_base_color} suits) × "
                f"{b_count} colors = {total_same_shade_cones} Cones"
            )

            cone_rows.append({
                "Needle": info["needle"],
                "Code": info.get("code", code),
                "Description": info["name"],
                "Category": "🟣 Matching (Same)",
                "Is_Same": True,
                "1 Suit (m)": round(m_1_suit, 1),
                "1 Frame (m)": round(m_1_frame, 0),
                "Cones / Suit": round(cones_per_suit, 4),
                "Per Color Cones": f"{int_cones_per_shade} Cones ({suits_per_base_color} suits)",
                "Kul Cones (🧵)": total_same_shade_cones,
                "Formula / Note": formula_note
            })

        else:
            # ─────────────────────────────────────────────────────────────
            # COMMON DHAGA FORMULA:
            # Runs across all suits in the order (num_pieces)!
            # ─────────────────────────────────────────────────────────────
            exact_cones_order = cones_per_suit * num_pieces * waste_mult
            int_cones_order = math.ceil(exact_cones_order) if exact_cones_order > 0 else 1

            total_common_cones_int += int_cones_order
            total_order_cones_int += int_cones_order
            total_order_cones_exact += exact_cones_order

            formula_note = f"Poori Lot ({num_pieces} suits) = {int_cones_order} Cones"

            cone_rows.append({
                "Needle": info["needle"],
                "Code": info.get("code", code),
                "Description": info["name"],
                "Category": "🔵 Common Dhaaga",
                "Is_Same": False,
                "1 Suit (m)": round(m_1_suit, 1),
                "1 Frame (m)": round(m_1_frame, 0),
                "Cones / Suit": round(cones_per_suit, 4),
                "Per Color Cones": "— (Poori Lot)",
                "Kul Cones (🧵)": int_cones_order,
                "Formula / Note": formula_note
            })

    # Machine runs & timing
    effective_spm = machine_rpm * DEFAULT_EFFICIENCY
    part_runs_details = {}
    total_runs = 0
    total_hours = 0.0

    if parts:
        for h, p in parts.items():
            p_st = int(round(p.get("stitches", 0)))
            p_rep = float(p.get("repeat", 1.0))
            cfg = p.get("cfg") or compute_part_heads_config(
                f"{p.get('design_name', '')} {p.get('file_name', '')}",
                p_rep,
                machine_heads,
                base_colors_count,
                p
            )

            mode = cfg["mode"]
            def_h = max(1, machine_heads)
            p_rep = float(cfg["repeat"])
            c_in_rep = max(1, cfg.get("colors_in_rep", 1))

            # Factory Repeat Rule:
            # 1 Lot me har color par design p_rep baar chalta hai:
            # Runs per lot = p_rep * (b_count / c_in_rep)
            # Total runs across entire order = (Runs per lot) * (num_pieces / (machine_heads * b_count))
            pieces_per_lot_calc = max(1, def_h * b_count)
            lots_calc = num_pieces / float(pieces_per_lot_calc)
            p_runs = max(1, int(round(p_rep * (b_count / float(c_in_rep)) * lots_calc))) if p_rep > 0 else 0
            p_runs_clr = round(p_runs / float(b_count), 1) if b_count > 0 else p_runs

            p_st_suit = int(round(p_st * cfg["rate_st_mult"]))
            p_rate_piece = (p_st_suit / 1000.0) * stitch_rate

            p_mins_per_batch = (p_st / effective_spm) if effective_spm > 0 else 0
            p_batch_hours = (p_mins_per_batch / 60.0) * p_runs

            total_runs += p_runs
            total_hours += p_batch_hours

            part_runs_details[h] = {
                "name": p.get("design_name", "Part"),
                "mode": mode,
                "repeat": cfg["repeat"],
                "badge": cfg["badge"],
                "runs": p_runs,
                "runs_per_color": p_runs_clr,
                "hours": round(p_batch_hours, 1),
                "suit_stitches": p_st_suit,
                "rate_per_piece": round(p_rate_piece, 2),
                "total_amount": round(p_rate_piece * num_pieces, 2)
            }

        shifts_needed = round(total_hours / shift_hours, 1) if shift_hours > 0 else 0
        days_needed = round(shifts_needed / 2.0, 1)
    else:
        total_runs = math.ceil(num_pieces / machine_heads) if machine_heads > 0 else 0
        minutes_per_batch = (total_suit_stitches / effective_spm) if effective_spm > 0 else 0
        total_hours = (minutes_per_batch / 60.0) * total_runs
        shifts_needed = round(total_hours / shift_hours, 1) if shift_hours > 0 else 0
        days_needed = round(shifts_needed / 2.0, 1)

    # Financial Costing (1 Piece Rate: total suit stitches * stitch_rate / 1000)
    piece_rate = (total_suit_stitches / 1000.0) * stitch_rate
    total_order_amount = piece_rate * num_pieces

    return {
        "cone_rows": cone_rows,
        "total_order_cones": total_order_cones_int,
        "total_order_cones_exact": round(total_order_cones_exact, 2),
        "total_common_cones": total_common_cones_int,
        "total_same_cones": total_same_cones_int,
        "suits_per_base_color": suits_per_base_color,
        "frames_per_base_color": frames_per_base_color,
        "total_runs": total_runs,
        "shifts_needed": shifts_needed,
        "days_needed": days_needed,
        "part_runs_details": part_runs_details,
        "piece_rate": piece_rate,
        "total_order_amount": total_order_amount,
        "stitching_cost_suit": piece_rate,
        "cost_per_suit": piece_rate,
        "total_order_cost": total_order_amount,
        "thread_cost_suit": 0.0,
        "bobbin_cost_suit": 0.0,
    }
