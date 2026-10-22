"""
Production Calculation Engine for Embroidery Operations.
Implements 3-Level Hierarchy (1 Suit -> Machine Frame -> Lot)
and Common vs Tone-on-Tone ('Same / Same Up / Same Lite') Cones Requisition.
Accurately scales across multiple lots (e.g. 1 lot = 180 pcs, 3 lots = 540 pcs).
"""

import math
import re
from core.config import (
    YARDS_TO_METERS,
    METERS_TO_YARDS,
    DEFAULT_EFFICIENCY,
    DEFAULT_BOBBIN_RATE_PER_METER,
    DEFAULT_MACHINE_HEADS
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


def aggregate_suit_parts(parts: dict, include_boring: bool = False, default_heads: int = DEFAULT_MACHINE_HEADS) -> tuple[int, int, float, dict]:
    """
    Sums up 1 Suit's total stitches, sequins, bobbin, and thread consumption across all parts.
    Also tracks 1 Frame thread meters according to each part's active heads (e.g. 30 vs 15 heads).
    When active heads is half (e.g. 15 on 30 head machine), 1 repeat on the machine produces 15 pieces,
    so for 30 suits of that color, 2 repeats make 30 pieces (1.0 piece per suit).
    Therefore: suit_mult = rep * (p_heads / default_heads).
    """
    total_stitches = 0
    total_sequins = 0
    total_bobbin_m = 0.0
    colors_dict = {}

    def_h = max(1, default_heads)

    for _, p in parts.items():
        rep = float(p.get("repeat", 1.0))
        p_heads = int(p.get("heads", def_h))
        if p_heads <= 0:
            p_heads = def_h

        # Effective pieces of this part in 1 complete suit
        # E.g. Silk Front (2 R, 15 heads on 30 head machine): suit_mult = 2.0 * (15/30) = 1.0 piece
        # Bazu (1.5 R, 30 heads on 30 head machine): suit_mult = 1.5 * (30/30) = 1.5 pieces
        suit_mult = rep * (p_heads / def_h)

        total_stitches += int(round(p.get("stitches", 0) * suit_mult))
        total_sequins += int(round(p.get("sequins_total", 0) * suit_mult))
        total_bobbin_m += float(p.get("total_bobbin_m", 0.0)) * suit_mult

        for tc in p.get("thread_colors", []):
            raw_code = str(tc.get("code", "")).strip()
            raw_name = str(tc.get("name", "")).strip() or raw_code
            length_single = float(tc.get("length_m", 0.0))
            needle = int(tc.get("needle", 1))

            if is_boring_tool(raw_code, raw_name) and not include_boring:
                continue

            # Normalized representations (trim spaces, uppercase for comparison)
            norm_code = re.sub(r'\s+', ' ', raw_code).strip()
            norm_name = re.sub(r'\s+', ' ', raw_name).strip() or norm_code
            code_upper = norm_code.upper()
            name_upper = norm_name.upper()

            # Find matching existing thread color:
            # 1. Exact case-insensitive code match (e.g. 'pink' == 'Pink' == 'PINK')
            # 2. Or same needle AND same description (e.g. Needle 2 and 'Tilla =6')
            target_key = None
            for ex_k, ex_info in colors_dict.items():
                ex_code_upper = ex_info["code"].strip().upper()
                ex_name_upper = ex_info["name"].strip().upper()
                ex_needle = ex_info["needle"]

                # Code match (if code is meaningful)
                if code_upper and code_upper not in ("-", "NONE", "N/A", "NULL") and code_upper == ex_code_upper:
                    target_key = ex_k
                    break

                # Same needle and same description
                if needle == ex_needle and name_upper == ex_name_upper:
                    target_key = ex_k
                    break

                # Same needle and code matches description or vice-versa
                if needle == ex_needle and (code_upper == ex_name_upper or name_upper == ex_code_upper):
                    target_key = ex_k
                    break

            if not target_key:
                # Use uppercase code or N{needle}_{name} as unique dict key
                target_key = code_upper if (code_upper and code_upper not in ("-", "NONE", "N/A")) else f"N{needle}_{name_upper}"
                
                # Title-case lowercase word codes (e.g. 'pink' -> 'Pink', but keep '3084' as is)
                display_code = norm_code.capitalize() if (norm_code.islower() and not norm_code.isdigit()) else norm_code
                display_name = norm_name if norm_name else display_code

                colors_dict[target_key] = {
                    "needle": needle,
                    "code": display_code,
                    "name": display_name,
                    "is_same": is_same_color(raw_code, raw_name),
                    "meters_1_suit": 0.0,
                    "meters_1_frame": 0.0,
                    "active_heads": p_heads
                }
            else:
                # Upgrade display code if current is capitalized and existing was lowercase
                cur_code = colors_dict[target_key]["code"]
                if cur_code.islower() and not norm_code.islower():
                    colors_dict[target_key]["code"] = norm_code

                # Upgrade display name if current has a better description
                cur_name = colors_dict[target_key]["name"]
                if (not cur_name or cur_name.upper() == code_upper) and norm_name and norm_name.upper() != code_upper:
                    colors_dict[target_key]["name"] = norm_name

                # Retain is_same flag if any part marks it as same
                if is_same_color(raw_code, raw_name):
                    colors_dict[target_key]["is_same"] = True

            colors_dict[target_key]["meters_1_suit"] += length_single * suit_mult
            colors_dict[target_key]["meters_1_frame"] += length_single * p_heads
            colors_dict[target_key]["active_heads"] = max(colors_dict[target_key].get("active_heads", 0), p_heads)

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
    cone_price: float,
    machine_rpm: int,
    shift_hours: float,
    parts: dict = None
) -> dict:
    """
    Executes production and cone calculations.
    For Same colors:
      - Pieces per base color = num_pieces / base_colors_count (e.g. 540 / 6 = 90 suits per color)
      - Cones per color shade = (1 Suit Meters ÷ Cone Cap) × Pieces per base color × (1 + waste%)
      - Total Cones = Cones per shade × base_colors_count
    For Common colors:
      - Runs on ALL suits = (1 Suit Meters ÷ Cone Cap) × num_pieces × (1 + waste%)
    """
    if "Yards" in cone_unit:
        cone_cap_m = cone_capacity_val * YARDS_TO_METERS
        cone_cap_yd = cone_capacity_val
    else:
        cone_cap_m = cone_capacity_val
        cone_cap_yd = cone_capacity_val * METERS_TO_YARDS

    waste_mult = 1.0 + (waste_pct / 100.0)

    # Calculate suits per base color (e.g. 540 / 6 = 90 suits)
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

        # Level 2: 1 Machine Frame (uses active heads from parts)
        m_1_frame = info.get("meters_1_frame", m_1_suit * machine_heads)
        yd_1_frame = m_1_frame * METERS_TO_YARDS

        is_same = info.get("is_same", False)

        # Cones per single suit (e.g. 3378 / 2770 = 1.2195)
        if "Yards" in cone_unit:
            cones_per_suit = yd_1_suit / cone_cap_yd if cone_cap_yd > 0 else 0
        else:
            cones_per_suit = m_1_suit / cone_cap_m if cone_cap_m > 0 else 0

        if is_same:
            # ─────────────────────────────────────────────────────────────
            # SAME / TONE-ON-TONE FORMULA:
            # Runs ONLY on its base color ({suits_per_base_color} pieces)!
            # E.g. 3 lots = 90 pieces per color -> 1.2195 × 90 = 109.76 -> 110 cones per shade!
            # Total for 6 shades = 110 × 6 = 660 Cones!
            # ─────────────────────────────────────────────────────────────
            exact_cones_per_shade = cones_per_suit * suits_per_base_color * waste_mult
            int_cones_per_shade = math.ceil(exact_cones_per_shade) if exact_cones_per_shade > 0 else 1

            total_same_shade_cones = int_cones_per_shade * b_count
            total_same_cones_int += total_same_shade_cones
            total_order_cones_int += total_same_shade_cones
            total_order_cones_exact += (exact_cones_per_shade * b_count)

            formula_note = (
                f"{int_cones_per_shade} Cones / shade ({suits_per_base_color} pcs) × "
                f"{b_count} colors = {total_same_shade_cones} Cones"
            )

            cone_rows.append({
                "Needle": info["needle"],
                "Code": info.get("code", code),
                "Description": info["name"],
                "Category": "🟣 Same (Base Match)",
                "Is_Same": True,
                "1 Suit (m)": round(m_1_suit, 1),
                "1 Frame (m)": round(m_1_frame, 0),
                "Cones / Suit": round(cones_per_suit, 3),
                "Per Color Cones": f"{int_cones_per_shade} Cones ({suits_per_base_color} pcs)",
                "Kul Cones (🧵)": total_same_shade_cones,
                "Formula / Note": formula_note
            })

        else:
            # ─────────────────────────────────────────────────────────────
            # COMMON COLOR FORMULA:
            # Runs across ALL suits in the entire order ({num_pieces})!
            # E.g. 540 suits -> (1 Suit Meters ÷ Cone Cap) × 540
            # ─────────────────────────────────────────────────────────────
            exact_cones_order = cones_per_suit * num_pieces * waste_mult
            int_cones_order = math.ceil(exact_cones_order) if exact_cones_order > 0 else 1

            total_common_cones_int += int_cones_order
            total_order_cones_int += int_cones_order
            total_order_cones_exact += exact_cones_order

            formula_note = f"Poori Lot ({num_pieces} pcs) = {int_cones_order} Cones"

            cone_rows.append({
                "Needle": info["needle"],
                "Code": info.get("code", code),
                "Description": info["name"],
                "Category": "🔵 Common Thread",
                "Is_Same": False,
                "1 Suit (m)": round(m_1_suit, 1),
                "1 Frame (m)": round(m_1_frame, 0),
                "Cones / Suit": round(cones_per_suit, 3),
                "Per Color Cones": "— (Poori Lot)",
                "Kul Cones (🧵)": int_cones_order,
                "Formula / Note": formula_note
            })

    # Machine runs & timing (Calculated per part based on active heads)
    effective_spm = machine_rpm * DEFAULT_EFFICIENCY
    part_runs_details = {}

    if parts:
        total_runs = 0
        total_hours = 0.0
        for h, p in parts.items():
            p_st = int(round(p.get("stitches", 0)))
            p_rep = float(p.get("repeat", 1.0))
            p_heads = int(p.get("heads", machine_heads))
            if p_heads <= 0:
                p_heads = machine_heads

            # Repeats (Chakar) needed for this part:
            # In Pakistani embroidery factories, p_rep is the machine repeats per color.
            # E.g. Silk Bazu (1.5 R) -> 1.5 * 6 = 9 Repeats (1.5 / color)
            # Silk Front (2 R, 15H Double Head) -> 2.0 * 6 = 12 Repeats (2.0 / color)
            # Velvet Patches (1 R) -> 1.0 * 6 = 6 Repeats (1.0 / color)
            def_h = max(1, machine_heads)
            p_runs = math.ceil(p_rep * (num_pieces / def_h))
            p_runs_per_color = round(p_rep * (suits_per_base_color / def_h), 1)

            # Timing for this part
            p_mins_per_batch = (p_st / effective_spm) if effective_spm > 0 else 0
            p_batch_hours = (p_mins_per_batch / 60.0) * p_runs

            total_runs += p_runs
            total_hours += p_batch_hours

            part_runs_details[h] = {
                "name": p.get("design_name", "Part"),
                "repeat": p_rep,
                "heads": p_heads,
                "runs": p_runs,
                "runs_per_color": p_runs_per_color,
                "hours": round(p_batch_hours, 1)
            }

        shifts_needed = round(total_hours / shift_hours, 1) if shift_hours > 0 else 0
        days_needed = round(shifts_needed / 2.0, 1)
    else:
        total_runs = math.ceil(num_pieces / machine_heads) if machine_heads > 0 else 0
        minutes_per_batch = (total_suit_stitches / effective_spm) if effective_spm > 0 else 0
        total_hours = (minutes_per_batch / 60.0) * total_runs
        shifts_needed = round(total_hours / shift_hours, 1) if shift_hours > 0 else 0
        days_needed = round(shifts_needed / 2.0, 1)

    # Financial Costing (1 Piece Rate: total stitches * stitch_rate / 1000)
    piece_rate = (total_suit_stitches / 1000.0) * stitch_rate
    total_order_amount = piece_rate * num_pieces

    stitching_cost_suit = piece_rate
    cost_per_suit = piece_rate
    total_order_cost = total_order_amount
    thread_cost_suit = 0.0
    bobbin_cost_suit = 0.0

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
        "stitching_cost_suit": stitching_cost_suit,
        "thread_cost_suit": thread_cost_suit,
        "bobbin_cost_suit": bobbin_cost_suit,
        "cost_per_suit": cost_per_suit,
        "total_order_cost": total_order_cost,
    }
