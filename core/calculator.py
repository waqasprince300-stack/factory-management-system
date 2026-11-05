"""
Production Calculation Engine for Embroidery Operations.
Implements Separate Systems for:
1. Dhaaga (Thread / Cones) Calculation
2. Stitch / 1 Piece Rate Calculation (per 1,000 stitches)
3. Backing Material (Bukram / Paper / Tarpin Rolls) Calculation
4. Machine Floor Timing & Needle Bar Sequence Map
5. Multi-Tier Costing vs Net Profit Analysis
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
    DOUBLE_HEAD_WIDTH_THRESHOLD_MM,
    DEFAULT_HEAD_PITCH_MM,
    DEFAULT_BUKRAM_ROLL_METERS,
    DEFAULT_BUKRAM_ROLL_PRICE,
    DEFAULT_BOBBIN_GRAMS_PER_MILLION_STITCHES,
    DEFAULT_COLOR_CHANGE_SECONDS,
    DEFAULT_FRAME_CHANGE_MINUTES,
    DEFAULT_REAL_RPM
)
from core.parser import extract_dual_shade


def is_same_color(code: str, name: str) -> bool:
    """
    Identifies if a thread color is tone-on-tone / base matching.
    Matches: 'same', 'sane', 'same up', 'same lite', 'same light', 'same dark', 'matching', 'base', 'tone'.
    """
    text = f"{code} {name}".lower()
    pattern = r'\b(same|sane|same\s*up|same\s*lite|same\s*light|same\s*dark|same\s*\d+|matching|base\s*match|tone)\b'
    return bool(re.search(pattern, text, re.I))


def is_boring_tool(code: str, name: str) -> bool:
    """
    Identifies if a needle is a boring knife rather than thread.
    Matches: 'bor', 'boring', 'borer', 'churi', 'knife', 'eyelet', 'punch', 'cutter'.
    """
    text = f"{code} {name}".lower()
    return bool(re.search(r'\b(bor|boring|borer|churi|chori|knife|eyelet|punch|cutter)\b', text, re.I))


def get_part_mode_options(machine_heads: int = DEFAULT_MACHINE_HEADS, base_colors: int = 6) -> dict:
    half_h = max(1, machine_heads // 2)
    nine_h = round(machine_heads / 3)
    four_h = round(machine_heads / max(1, base_colors))

    return {
        "1_rep_all": f"1 Repeat — Saray Head ({machine_heads}H)",
        "1_rep_half": f"1 Repeat — Half Head / Double Head ({half_h}H)",
        "half_rep_all": f"Half Repeat — 2 Colors Saray Head ({half_h}H)",
        "half_rep_half": f"Half Repeat — 2 Colors Half Head ({max(1, half_h // 2)}H)",
        "head_9": f"9 Head — 3 Colors / Frame (~{nine_h}H)",
        "head_4": f"4 Head — Base Colors / Frame (~{four_h}H)",
        "custom": "Custom Setting (Apni Marzi)"
    }


def compute_part_heads_config(
    target_name: str,
    repeat: float = 1.0,
    machine_heads: int = DEFAULT_MACHINE_HEADS,
    base_colors: int = 6,
    part_dict: dict = None
) -> dict:
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
            desc = f"{rep:g} Repeat — Double Head ({half_h} Heads) [Width: {width_val:g}mm > 450mm]"
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
        desc = f"{rep:g} Repeat — 2 Colors Saray Head (Har Color {half_h} Heads)"
        colors_in_rep = 2

    elif mode == "half_rep_half":
        h = quarter_h
        thread_h = float(quarter_h)
        rate_mult = rep
        badge = f"{rep:g}R · 2 Clr Half Head ({quarter_h}H)"
        badge_type = "double"
        desc = f"{rep:g} Repeat — 2 Colors Half Head (Har Color {quarter_h} Heads)"
        colors_in_rep = 2

    elif mode == "head_9":
        colors_in_rep = 3
        heads_exact = def_h / float(colors_in_rep)
        h = round(heads_exact)
        thread_h = heads_exact
        rate_mult = rep / float(colors_in_rep)
        badge = f"{rep:g}R · 9 Head ({h}H)"
        badge_type = "multi"
        desc = f"{rep:g} Repeat — 9 Head Mode (3 Colors/Frame, Stitches ÷ 3)"

    elif mode == "head_4":
        colors_in_rep = b_col
        heads_exact = def_h / float(colors_in_rep)
        h = round(heads_exact)
        thread_h = heads_exact
        rate_mult = rep / float(colors_in_rep)
        badge = f"{rep:g}R · 4 Head ({h}H)"
        badge_type = "multi"
        desc = f"{rep:g} Repeat — 4 Head Mode ({b_col} Colors/Frame, Stitches ÷ {b_col})"

    else:
        # custom
        h = int(part_d.get("heads", def_h))
        thread_h = float(h)
        rate_mult = rep * (h / float(def_h))
        badge = f"{rep:g}R · Custom ({h}H)"
        badge_type = "standard"
        desc = f"{rep:g} Repeat — Custom {h} Heads"
        colors_in_rep = max(1, round(def_h / float(max(1, h))))

    return {
        "mode": mode,
        "repeat": rep,
        "heads": h,
        "thread_heads": thread_h,
        "rate_st_mult": rate_mult,
        "badge": badge,
        "badge_type": badge_type,
        "desc": desc,
        "colors_in_rep": colors_in_rep
    }


def aggregate_suit_parts(
    parts: dict,
    include_boring: bool = False,
    default_heads: int = DEFAULT_MACHINE_HEADS,
    base_colors: int = 6
) -> tuple[int, int, float, dict]:
    total_suit_stitches = 0
    total_suit_sequins = 0
    total_suit_bobbin_m = 0.0
    colors_dict = {}

    for p_key, p in parts.items():
        st_single = float(p.get("stitches", 0.0))
        sq_single = float(p.get("sequins_total", 0.0))
        bob_single = float(p.get("total_bobbin_m", 0.0))
        p_rep = float(p.get("repeat", 1.0))

        cfg = compute_part_heads_config(
            f"{p.get('design_name', '')} {p.get('file_name', '')}",
            p_rep,
            default_heads,
            base_colors,
            p
        )
        p["cfg"] = cfg

        rate_mult = cfg["rate_st_mult"]
        total_suit_stitches += int(round(st_single * rate_mult))
        total_suit_sequins += int(round(sq_single * rate_mult))
        total_suit_bobbin_m += bob_single * rate_mult

        for tc in p.get("thread_colors", []):
            raw_code = str(tc.get("code", "")).strip()
            raw_name = str(tc.get("name", "")).strip() or raw_code
            length_single = float(tc.get("length_m", 0.0))
            needle = int(tc.get("needle", 1))

            if is_boring_tool(raw_code, raw_name) and not include_boring:
                continue

            clean_code, clean_name, check_c = extract_dual_shade(raw_code, raw_name)
            final_check = tc.get("check_code") or check_c
            if check_c:
                raw_code = clean_code
                raw_name = clean_name
                tc["code"] = clean_code
                tc["name"] = clean_name
                tc["check_code"] = check_c

            part_suit_m = length_single * cfg["rate_st_mult"]
            part_frame_m = length_single * cfg["thread_heads"] * cfg["repeat"]

            norm_code = re.sub(r'\s+', ' ', raw_code).strip()
            norm_name = re.sub(r'\s+', ' ', raw_name).strip() or norm_code
            code_upper = norm_code.upper()
            name_upper = norm_name.upper()

            target_key = None
            has_valid_code = bool(code_upper and code_upper not in ("-", "NONE", "N/A", "NULL", ""))

            for ex_k, ex_info in colors_dict.items():
                ex_code_upper = ex_info["code"].strip().upper()
                ex_name_upper = ex_info["name"].strip().upper()
                ex_needle = ex_info["needle"]
                ex_has_valid_code = bool(ex_code_upper and ex_code_upper not in ("-", "NONE", "N/A", "NULL", ""))

                # Rule 1: If both have valid shade codes, merge ONLY if code matches exactly
                if has_valid_code and ex_has_valid_code:
                    if code_upper == ex_code_upper:
                        target_key = ex_k
                        break
                    else:
                        # Distinct shade codes (e.g. 3019 vs 3020) must NEVER merge!
                        continue

                # Rule 2: If one or both lack a valid code, merge by non-generic shade name if needle matches
                GENERIC_NAMES = {"CD", "COLOR", "THREAD", "NONE", "N/A", "-", "", "1", "2", "3", "4", "5", "6", "7", "8", "9"}
                if name_upper and name_upper not in GENERIC_NAMES and name_upper == ex_name_upper:
                    target_key = ex_k
                    break

                # Rule 3: Cross code-to-name match
                if has_valid_code and not ex_has_valid_code and code_upper == ex_name_upper:
                    target_key = ex_k
                    break
                if not has_valid_code and ex_has_valid_code and name_upper == ex_code_upper:
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
                    "check_code": final_check,
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
                if not colors_dict[target_key].get("check_code") and final_check:
                    colors_dict[target_key]["check_code"] = final_check

            colors_dict[target_key]["meters_1_suit"] += part_suit_m
            colors_dict[target_key]["meters_1_frame"] += part_frame_m
            colors_dict[target_key]["active_heads"] = max(
                colors_dict[target_key]["active_heads"],
                cfg["heads"]
            )

    return total_suit_stitches, total_suit_sequins, total_suit_bobbin_m, colors_dict


def calculate_full_production(
    total_suit_stitches: int,
    total_suit_bobbin_m: float,
    colors_dict: dict,
    machine_heads: int = DEFAULT_MACHINE_HEADS,
    base_colors_count: int = 6,
    num_pieces: int = 180,
    lots_count: float = 1.0,
    cone_capacity_val: float = 2700.0,
    cone_unit: str = "Meters",
    waste_pct: float = 0.0,
    stitch_rate: float = 1.0,
    cone_price: float = DEFAULT_CONE_PRICE,
    machine_rpm: float = DEFAULT_MACHINE_RPM,
    shift_hours: float = DEFAULT_SHIFT_HOURS,
    parts: dict = None,
    pitch_mm: float = DEFAULT_HEAD_PITCH_MM,
    bukram_roll_meters: float = DEFAULT_BUKRAM_ROLL_METERS,
    bukram_price_per_roll: float = DEFAULT_BUKRAM_ROLL_PRICE,
    other_cost_per_suit: float = 40.0,
    bobbin_cone_capacity_val: float = 10000.0
) -> dict:
    cone_cap_m = cone_capacity_val if "meter" in cone_unit.lower() else (cone_capacity_val * YARDS_TO_METERS)
    waste_mult = 1.0 + (waste_pct / 100.0)

    b_count = max(1, base_colors_count)
    suits_per_base_color = int(round(num_pieces / float(b_count)))
    frames_per_base_color = int(math.ceil(suits_per_base_color / float(max(1, machine_heads))))

    cone_rows = []
    total_order_cones_int = 0
    total_order_cones_exact = 0.0
    total_common_cones_int = 0
    total_same_cones_int = 0

    for code, info in colors_dict.items():
        m_1_suit = info["meters_1_suit"]
        m_1_frame = info["meters_1_frame"]
        is_same = info["is_same"]
        chk_code = info.get("check_code")

        cones_per_suit = (m_1_suit / cone_cap_m) if cone_cap_m > 0 else 0.0
        chk_suffix = f" [Check: {chk_code}]" if chk_code else ""

        if is_same:
            exact_cones_per_shade = cones_per_suit * suits_per_base_color * waste_mult
            int_cones_per_shade = math.ceil(exact_cones_per_shade) if exact_cones_per_shade > 0 else 1
            total_same_shade_cones = int_cones_per_shade * b_count

            total_same_cones_int += total_same_shade_cones
            total_order_cones_int += total_same_shade_cones
            total_order_cones_exact += (exact_cones_per_shade * b_count)

            formula_note = f"{int_cones_per_shade} Cones / Color × {b_count} Colors = {total_same_shade_cones} Cones{chk_suffix}"

            cone_rows.append({
                "Needle": info["needle"],
                "Code": info.get("code", code),
                "Description": info["name"],
                "Check_Code": chk_code,
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
            exact_cones_order = cones_per_suit * num_pieces * waste_mult
            int_cones_order = math.ceil(exact_cones_order) if exact_cones_order > 0 else 1

            total_common_cones_int += int_cones_order
            total_order_cones_int += int_cones_order
            total_order_cones_exact += exact_cones_order

            formula_note = f"Poori Lot ({num_pieces} suits) = {int_cones_order} Cones{chk_suffix}"

            cone_rows.append({
                "Needle": info["needle"],
                "Code": info.get("code", code),
                "Description": info["name"],
                "Check_Code": chk_code,
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

            part_heads = max(1, int(cfg.get("heads", def_h)))
            pieces_per_frame = part_heads * c_in_rep
            total_part_pieces_needed = num_pieces * p_rep
            p_runs = max(1, int(math.ceil(total_part_pieces_needed / float(pieces_per_frame)))) if p_rep > 0 else 0
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

    # 1. Backing Material (Bukram / Paper / Tarpin) Calculation
    frame_length_m = ((machine_heads * pitch_mm) / 1000.0) + 0.5
    total_bukram_m = round(total_runs * frame_length_m, 1)
    bukram_rolls_exact = (total_bukram_m / bukram_roll_meters) if bukram_roll_meters > 0 else 0.0
    bukram_rolls_int = math.ceil(bukram_rolls_exact) if bukram_rolls_exact > 0 else 1
    bukram_cost_order = bukram_rolls_int * bukram_price_per_roll
    bukram_cost_suit = round(bukram_cost_order / max(1, num_pieces), 2)

    # 2. Bobbin (Khicha) in Grams & Cones
    grand_stitches = total_suit_stitches * num_pieces
    bobbin_grams = round((grand_stitches / 1_000_000.0) * DEFAULT_BOBBIN_GRAMS_PER_MILLION_STITCHES, 0)
    bobbin_kg = round(bobbin_grams / 1000.0, 2)
    order_bobbin_m = float(total_suit_bobbin_m) * num_pieces * waste_mult
    if order_bobbin_m <= 0 and grand_stitches > 0:
        # Standard factory estimate: ~3.5 meters bobbin per 1,000 stitches
        order_bobbin_m = (grand_stitches / 1000.0) * 3.5 * waste_mult
    b_cap = max(100.0, float(bobbin_cone_capacity_val))
    bobbin_cones = math.ceil(order_bobbin_m / b_cap) if order_bobbin_m > 0 else 0
    bobbin_cost_order = bobbin_cones * 320.0
    bobbin_cost_suit = round(bobbin_cost_order / max(1, num_pieces), 2)

    # 3. Needle Bar Sequence Map (1 to 15)
    needle_bar_map = []
    seen_needles = set()
    for row in sorted(cone_rows, key=lambda x: x["Needle"]):
        n = row["Needle"]
        if n not in seen_needles:
            seen_needles.add(n)
            code_str = str(row["Code"])
            desc_str = str(row["Description"])

            tooling = "Resham (Viscose)"
            if any(w in f"{code_str} {desc_str}".lower() for w in ["tilla", "sona", "chandi", "zari", "gold"]):
                tooling = "Tilla (Metallic)"
            elif any(w in f"{code_str} {desc_str}".lower() for w in ["bor", "boring", "churi", "knife"]):
                tooling = "Boring Knife"
            elif any(w in f"{code_str} {desc_str}".lower() for w in ["sitara", "sequin"]):
                tooling = "Sitara (Sequin)"
            elif row.get("Is_Same"):
                tooling = "Matching (Same Base)"

            needle_bar_map.append({
                "needle": n,
                "code": code_str,
                "name": desc_str,
                "check_code": row.get("Check_Code"),
                "category": row["Category"],
                "tooling": tooling,
                "is_same": row.get("Is_Same", False),
                "cones": row.get("Kul Cones (🧵)", 0),
                "m_1_suit": row.get("1 Suit (m)", 0.0)
            })

    # Include any boring knife needles in operator needle setup card (with 0 thread cones)
    if parts:
        for p in parts.values():
            for tc in p.get("thread_colors", []):
                rc = str(tc.get("code", "")).strip()
                rn = str(tc.get("name", "")).strip() or rc
                n = int(tc.get("needle", 1))
                if is_boring_tool(rc, rn) and n not in seen_needles:
                    seen_needles.add(n)
                    needle_bar_map.append({
                        "needle": n,
                        "code": rc,
                        "name": rn,
                        "check_code": None,
                        "category": "🔪 Boring Knife",
                        "tooling": "Boring Knife",
                        "is_same": False,
                        "cones": 0,
                        "m_1_suit": 0.0
                    })

    needle_bar_map.sort(key=lambda x: x["needle"])

    # 4. Real Factory Timing (Factoring Color Changes & Takaai/Frame Changes)
    num_color_changes = max(1, len(needle_bar_map))
    real_spm = float(machine_rpm) if (machine_rpm is not None and float(machine_rpm) > 0) else float(DEFAULT_REAL_RPM)
    
    # Pure stitching minutes: exact sum of each part's stitching time across its actual runs
    if parts:
        stitching_mins_total = sum(
            ((float(p.get("stitches", 0)) / real_spm) * part_runs_details[h]["runs"])
            for h, p in parts.items()
            if h in part_runs_details
        ) if real_spm > 0 else 0.0
    else:
        stitching_mins_total = (total_suit_stitches / real_spm) * total_runs if real_spm > 0 else 0.0

    color_change_loss_mins = (num_color_changes * DEFAULT_COLOR_CHANGE_SECONDS / 60.0) * total_runs
    frame_change_loss_mins = DEFAULT_FRAME_CHANGE_MINUTES * total_runs
    pure_stitch_hours = round(stitching_mins_total / 60.0, 1)
    real_total_hours = round((stitching_mins_total + color_change_loss_mins + frame_change_loss_mins) / 60.0, 1)
    real_shifts = max(1, int(math.ceil(real_total_hours / shift_hours)))
    real_days = round(real_shifts / 2.0, 1)

    # 5. Financial Costing vs Net Profit (Munafa)
    piece_rate = (total_suit_stitches / 1000.0) * stitch_rate
    total_order_amount = piece_rate * num_pieces

    dhaaga_cost_order = total_order_cones_int * cone_price
    dhaaga_cost_suit = round(dhaaga_cost_order / max(1, num_pieces), 2)
    other_cost_order = other_cost_per_suit * num_pieces

    total_cost_per_suit = round(dhaaga_cost_suit + bobbin_cost_suit + bukram_cost_suit + other_cost_per_suit, 2)
    total_order_cost = round(total_cost_per_suit * num_pieces, 2)
    net_profit_per_suit = round(piece_rate - total_cost_per_suit, 2)
    total_order_profit = round(net_profit_per_suit * num_pieces, 2)

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
        "pure_stitch_hours": pure_stitch_hours,
        "real_total_hours": real_total_hours,
        "real_shifts": real_shifts,
        "real_days": real_days,
        "color_change_loss_mins": color_change_loss_mins,
        "frame_change_loss_mins": frame_change_loss_mins,
        "part_runs_details": part_runs_details,
        "piece_rate": piece_rate,
        "total_order_amount": total_order_amount,
        # Bukram / Backing
        "frame_length_m": frame_length_m,
        "total_bukram_m": total_bukram_m,
        "bukram_rolls_exact": bukram_rolls_exact,
        "bukram_rolls_int": bukram_rolls_int,
        "bukram_cost_suit": bukram_cost_suit,
        "bukram_cost_order": bukram_cost_order,
        # Bobbin weight
        "bobbin_grams": bobbin_grams,
        "bobbin_kg": bobbin_kg,
        "bobbin_cones": bobbin_cones,
        "order_bobbin_m": order_bobbin_m,
        "bobbin_cost_suit": bobbin_cost_suit,
        "bobbin_cost_order": bobbin_cost_order,
        # Needle Map
        "needle_bar_map": needle_bar_map,
        # Real Machine Floor Timing
        "real_spm": int(round(real_spm)),
        "real_total_hours": real_total_hours,
        "real_shifts": real_shifts,
        "real_days": real_days,
        "color_change_loss_mins": round(color_change_loss_mins, 0),
        "frame_change_loss_mins": round(frame_change_loss_mins, 0),
        # Costing & Profit
        "dhaaga_cost_suit": dhaaga_cost_suit,
        "dhaaga_cost_order": dhaaga_cost_order,
        "total_cost_per_suit": total_cost_per_suit,
        "total_order_cost": total_order_cost,
        "net_profit_per_suit": net_profit_per_suit,
        "total_order_profit": total_order_profit,
        "other_cost_per_suit": other_cost_per_suit
    }
