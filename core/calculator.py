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


def compute_part_heads_config(target_name: str, repeat: float, machine_heads: int, part_dict: dict = None) -> dict:
    """
    Determines active heads, badge, and suit multiplier based on Pakistani factory rules:
    - 9H / 4H Multi-color: multiple cloth colors combined on 1 repeat frame.
      - 28H with 9H -> 3 colors (2 of 9 heads, 1 of 10 heads)
      - 30H with 9H -> 3 colors of 10 heads each
      - 28H with 4H -> 7 colors of 4 heads each
      - 30H with 4H -> 7-8 colors (4H-5H each)
      Stitches per suit = 100% (1 suit receives 1 full piece).
    - Size split (S, M, L):
      Half heads (14 on 28H, 15 on 30H).
    - Double repeat:
      Half heads (14 on 28H, 15 on 30H).
    """
    target = str(target_name or "")
    part_d = part_dict or {}

    size_tag = part_d.get("size_tag")
    if not size_tag:
        size_m = re.search(r'\(\s*([sml])\s*\)', target, re.I)
        size_tag = size_m.group(1).upper() if size_m else None

    tag_heads = part_d.get("tag_heads")
    if not tag_heads:
        head_m = re.search(r'\(\s*(\d+)\s*(?:h|head|heads)\b', target, re.I)
        if not head_m:
            head_m = re.search(r'\b(\d+)\s*(?:h|head|heads)\b', target, re.I)
        tag_heads = int(head_m.group(1)) if head_m else None

    is_size_split = bool(size_tag) or part_d.get("is_size_split", False)
    is_multi_color = bool(tag_heads and tag_heads in range(2, 13) and not is_size_split)
    is_double = (
        (repeat >= 2.0) or
        is_size_split or
        part_d.get("is_double_repeat", False) or
        bool(re.search(r'\b(double|14\s*h|14\s*head|15\s*h|15\s*head)\b', target, re.I))
    )

    def_h = max(1, machine_heads)

    if is_multi_color and tag_heads:
        colors_in_repeat = max(1, round(def_h / tag_heads))
        base_h = def_h // colors_in_repeat
        rem_h = def_h % colors_in_repeat

        if rem_h == 0:
            badge = f"⚡ {colors_in_repeat} Colors / Repeat ({base_h}H each)"
            heads_display = f"{base_h}H"
            heads_desc = f"{base_h} heads per color"
        else:
            c_base = colors_in_repeat - rem_h
            c_ext = rem_h
            h_ext = base_h + 1
            badge = f"⚡ {colors_in_repeat} Colors / Repeat ({c_base}×{base_h}H + {c_ext}×{h_ext}H)"
            heads_display = f"{base_h}H-{h_ext}H"
            heads_desc = f"{c_base} colors of {base_h}H + {c_ext} color of {h_ext}H"

        return {
            "type": "multi_color",
            "heads": base_h,
            "badge": badge,
            "badge_type": "multi",
            "colors": colors_in_repeat,
            "tag_heads": tag_heads,
            "size_tag": None,
            "suit_mult": repeat * 1.0,
            "suit_multiplier": repeat * 1.0,
            "heads_display": heads_display,
            "heads_desc": heads_desc
        }

    elif is_double or is_size_split:
        h = max(1, def_h // 2)
        s_txt = f" (Size {size_tag})" if size_tag else ""
        badge = f"⚡ {h}H Double{s_txt}"
        return {
            "type": "double",
            "heads": h,
            "badge": badge,
            "badge_type": "double",
            "colors": 1,
            "tag_heads": tag_heads,
            "size_tag": size_tag,
            "suit_mult": repeat * (h / def_h),
            "suit_multiplier": repeat * (h / def_h),
            "heads_display": f"{h}H",
            "heads_desc": f"{h} heads alternate repeat"
        }

    else:
        return {
            "type": "standard",
            "heads": def_h,
            "badge": "",
            "badge_type": "standard",
            "colors": 1,
            "tag_heads": None,
            "size_tag": None,
            "suit_mult": repeat * 1.0,
            "suit_multiplier": repeat * 1.0,
            "heads_display": f"{def_h}H",
            "heads_desc": f"{def_h} full machine heads"
        }


def aggregate_suit_parts(parts: dict, include_boring: bool = False, default_heads: int = DEFAULT_MACHINE_HEADS) -> tuple[int, int, float, dict]:
    """
    Sums up 1 Suit's total stitches, sequins, bobbin, and thread consumption across all parts.
    Tracks 1 Frame thread meters according to each part's active heads:
    - Multi-color repeat (e.g. 9H): 1 suit gets 1 full piece (suit_mult = 1.0). Same thread runs on 9H, Common thread runs on 28H.
    - Size split (e.g. S, M, L) / Double-head: suit_mult = rep * (p_heads / def_h). Both Same and Common thread run on 14H.
    - Standard part: suit_mult = rep * 1.0. All thread runs on 28H.
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

        cfg = compute_part_heads_config(
            f"{p.get('design_name', '')} {p.get('file_name', '')}",
            rep,
            def_h,
            p
        )
        p_type = cfg["type"]

        if p_type == "multi_color":
            suit_mult = rep * 1.0
            same_heads = p_heads
            common_heads = def_h
        elif p_type == "double" or (p_heads < def_h):
            suit_mult = rep * (p_heads / def_h)
            same_heads = p_heads
            common_heads = p_heads
        else:
            suit_mult = rep * 1.0
            same_heads = def_h
            common_heads = def_h

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

            active_h = same_heads if is_same_color(raw_code, raw_name) else common_heads

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
                    "active_heads": active_h
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

            colors_dict[target_key]["meters_1_suit"] += length_single * suit_mult
            colors_dict[target_key]["meters_1_frame"] += length_single * active_h
            colors_dict[target_key]["active_heads"] = max(colors_dict[target_key].get("active_heads", 0), active_h)

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

            def_h = max(1, machine_heads)
            cfg = compute_part_heads_config(
                f"{p.get('design_name', '')} {p.get('file_name', '')}",
                p_rep,
                machine_heads,
                p
            )

            # Machine repeats (Chakar) needed for this part:
            if cfg["type"] == "multi_color":
                # Multi-color repeat: all machine heads run simultaneously across colors.
                p_runs = math.ceil(p_rep * (num_pieces / def_h))
                colors_in_rep = cfg.get("colors", 3)
                p_runs_per_color = round(p_rep * (suits_per_base_color / (def_h / colors_in_rep)), 1)
            elif cfg["type"] == "double" or p_heads < def_h:
                # Alternate/Double head repeat (14 on 28H, 15 on 30H)
                p_runs = math.ceil(p_rep * (num_pieces / p_heads))
                p_runs_per_color = round(p_rep * (suits_per_base_color / p_heads), 1)
            else:
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
                "hours": round(p_batch_hours, 1),
                "badge": cfg.get("badge", ""),
                "badge_type": cfg.get("badge_type", "standard")
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
