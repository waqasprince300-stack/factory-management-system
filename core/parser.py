"""
Document & Image Parsers for Wilcom Worksheets.
Extracts stitches, dimensions, repeats, bobbin, sequins, and thread table.
Auto-detects:
- Multi-color repeat grouping (e.g. 9 Head / 4 Head)
- Size-split / Double repeat (e.g. S, M, L)
"""

import io
import re
import pdfplumber
from PIL import Image, ImageOps
from core.config import MAX_PDF_PAGES, FEET_TO_METERS, YARDS_TO_METERS, DOUBLE_HEAD_WIDTH_THRESHOLD_MM
from core.security import sanitize_filename


def parse_repeat_token(token: str) -> float:
    """Helper to convert token string into repeat float value (supports half, double, quarter, 1/2, 1/4)."""
    t = str(token or "").strip().lower()
    if not t:
        return 1.0

    # Compound: 1+half, 1 + half, 1 and half, 1+1/2, 2+half
    m = re.match(r'^(\d+)\s*(?:\+|\band\b|\s)\s*(?:half|1/2)$', t)
    if m:
        return float(m.group(1)) + 0.5

    m = re.match(r'^(\d+)\s*(?:\+|\band\b|\s)\s*(?:quarter|1/4)$', t)
    if m:
        return float(m.group(1)) + 0.25

    if t in ("half", "1/2", ".5", "0.5"):
        return 0.5
    if t in ("double", "2"):
        return 2.0
    if t in ("quarter", "1/4", ".25", "0.25"):
        return 0.25

    try:
        val = float(t)
        if val > 0:
            return val
    except ValueError:
        pass
    return 1.0


def extract_repeat_from_text(text: str) -> float:
    """
    Extracts repeat count from text (e.g. '1+Half R', '[7 R]', '(7 R)', '{7 R}', '7 R', '7 Repeat', 'Repeat: 7', '7 rpeat', 'Half R', '0.5 R', 'Double Repeat').
    Supports compound fractions (1+half, 2+half, 1+1/2), prefix notation, square brackets, parentheses, curly braces, and unbracketed word boundaries.
    """
    t = str(text or "")

    # 1. Direct compound detection (e.g. '1+Half', '1 + half', '2+Half R', '(1+Half R)', '[1+half]')
    m = re.search(r'(\d+)\s*(?:\+|\band\b|\s)\s*(?:half|1/2)\s*(?:-?\s*r[a-z]*|x|times)?', t, re.I)
    if m:
        return float(m.group(1)) + 0.5

    m = re.search(r'(\d+)\s*(?:\+|\band\b|\s)\s*(?:quarter|1/4)\s*(?:-?\s*r[a-z]*|x|times)?', t, re.I)
    if m:
        return float(m.group(1)) + 0.25

    # 2. Prefix pattern: Repeat: 7, Repeats: 1.5, Repeat 1+half, Rpeat: 7
    m = re.search(r'\b(?:repeat|repeats|rpeat|rpeats)\s*[:=\-]?\s*(\d+(?:\.\d+)?|\bhalf\b|\bdouble\b|\bquarter\b)', t, re.I)
    if m:
        return parse_repeat_token(m.group(1))

    # 3. Bracketed pattern: [7 R], (7 R), {7 R}, [Half R], [1.5 R], [0.5 R], (2 R)
    m = re.search(r'[\[\(\{]\s*(\d+(?:\.\d+)?|\bhalf\b|\bdouble\b|\bquarter\b|1/2|1/4)\s*(?:-?\s*r[a-z]*|x|times)?\s*[\]\)\}]', t, re.I)
    if m:
        return parse_repeat_token(m.group(1))

    # 4. Unbracketed suffix: 7 R, 7-R, 7R, 1.5 R, 0.5 R, 7 Repeat, Half R, Double R
    m = re.search(r'\b(\d+(?:\.\d+)?|\bhalf\b|\bdouble\b|\bquarter\b|1/2|1/4)\s*(?:-?\s*(?:r|repeat|repeats|rpeat|rpeats|rept|times|chakkar|chaker)\b|x\b)', t, re.I)
    if m:
        return parse_repeat_token(m.group(1))

    # 5. Standalone double / half / quarter repeat words (ensure no preceding digits or operators)
    if re.search(r'(?<!\d)(?<!\+)\bdouble\s*(?:repeat|rpeat|chaker|chakkar)?\b', t, re.I):
        return 2.0
    if re.search(r'(?<!\d)(?<!\+)\bhalf\s*(?:repeat|rpeat|chaker|chakkar)?\b', t, re.I):
        return 0.5
    if re.search(r'(?<!\d)(?<!\+)\bquarter\s*(?:repeat|rpeat|chaker|chakkar)?\b', t, re.I):
        return 0.25

    return 1.0


def extract_part_attributes(name: str, repeat: float = 1.0, width_mm: float = 0.0) -> dict:
    """
    Extracts size split, multi-color head tags, and double repeat flags from design/file name:
    - Multi-color repeat: e.g. '(9 H)', '(4 Head)' -> tag_heads=9/4, is_multi_color_repeat=True
    - Size split: e.g. '(S)', '(M)', '(L)' -> size_tag='S'/'M'/'L', is_size_split=True, is_double_repeat=True
    - Double repeat / Double Head: width > 400mm, 2 R, 14H, 15H, 'double', or size split
    """
    target = str(name or "")

    # 1. Size split in brackets: (S), (M), (L)
    size_m = re.search(r'[\[\(\{]\s*([sml])\s*[\]\)\}]', target, re.I)
    size_tag = size_m.group(1).upper() if size_m else None

    # 2. Head tag in brackets or word: (9 H), [9 H], (4 Head), 9H, 4H, 14H
    head_m = re.search(r'[\[\(\{]\s*(\d+)\s*(?:h|head|heads)\b', target, re.I)
    if not head_m:
        head_m = re.search(r'\b(\d+)\s*(?:h|head|heads)\b', target, re.I)
    tag_heads = int(head_m.group(1)) if head_m else None

    is_size_split = bool(size_tag)
    # Multi-color repeat tag: heads between 2 and 12 (not half heads 14/15)
    is_multi_color_repeat = bool(tag_heads and tag_heads in range(2, 13) and not is_size_split)

    # Double repeat / Double Head: width > 450mm, 2 R, 14H, 15H, 'double', or size split (S, M, L)
    is_double_repeat = (
        (repeat >= 2.0) or
        (width_mm > DOUBLE_HEAD_WIDTH_THRESHOLD_MM) or
        is_size_split or
        bool(re.search(r'\b(double|14\s*h|14\s*head|15\s*h|15\s*head)\b', target, re.I))
    )

    return {
        "size_tag": size_tag,
        "tag_heads": tag_heads,
        "is_size_split": is_size_split,
        "is_multi_color_repeat": is_multi_color_repeat,
        "is_double_repeat": is_double_repeat
    }


def extract_dual_shade(raw_code: str, raw_name: str) -> tuple[str, str, str | None]:
    """
    Detects dual shade codes (e.g. '4118-3152', '4118/3152', '4118 - 3152')
    where digitizers specify two shade numbers:
    - 1st number is the Main Color (auto-picked for 100% thread/cone calculation).
    - 2nd number is for 1 Check Shirt / sample piece.
    Returns: (main_code, clean_name, check_code)
    """
    raw_c = str(raw_code or "").strip()
    raw_n = str(raw_name or "").strip()
    combined = f"{raw_c} {raw_n}".strip()

    # Pattern 1: Pure digits separated by - or / (e.g. 4118-3152, 4118 - 3152, 4118/3152)
    m = re.search(r'\b(\d{2,6})\s*[-/]\s*(\d{2,6})\b', combined)
    if not m:
        # Pattern 2: Slash between alphanumeric shade codes (e.g. M4118/M3152)
        m = re.search(r'\b([A-Za-z0-9]{2,8})\s*/\s*([A-Za-z0-9]{2,8})\b', combined)

    if m:
        main_c = m.group(1)
        check_c = m.group(2)

        clean_n = re.sub(r'\b' + re.escape(m.group(0)) + r'\b', '', raw_n).strip()
        clean_n = re.sub(r'^[-/\s]+|[-/\s]+$', '', clean_n).strip()

        if clean_n and clean_n.lower() not in (raw_c.lower(), main_c.lower(), check_c.lower()):
            final_name = f"{clean_n} (Check: {check_c})"
        else:
            final_name = f"{main_c} (Check: {check_c})"

        return main_c, final_name, check_c

    return raw_c, raw_n or raw_c, None


def _extract_page_data(p, clean_name: str, page_idx: int = 0) -> dict:
    """Extracts raw text, stitches, dimensions, and thread table from a single PDF page."""
    words = p.extract_words()
    full_text = p.extract_text(layout=False) or ""

    # Design Name
    dm = re.search(r'Design:\s*(.*?)(?:\n|$)', full_text)
    design_name = dm.group(1).strip() if dm else None

    # Stitches
    sm = re.search(r'Stitches:\s*([\d,]+)', full_text)
    stitches = int(sm.group(1).replace(",", "")) if sm else 0

    # Dimensions (Supports mm and inches conversion: 1 in = 25.4 mm)
    hm = re.search(r'Height:\s*([\d,]+(?:\.\d+)?)\s*(mm|in|inch|inches)?', full_text, re.I)
    height_mm = 0.0
    if hm:
        raw_h = float(hm.group(1).replace(",", ""))
        u_h = (hm.group(2) or "mm").lower()
        height_mm = round(raw_h * 25.4, 2) if u_h in ("in", "inch", "inches") else round(raw_h, 2)

    wm = re.search(r'Width:\s*([\d,]+(?:\.\d+)?)\s*(mm|in|inch|inches)?', full_text, re.I)
    width_mm = 0.0
    if wm:
        raw_w = float(wm.group(1).replace(",", ""))
        u_w = (wm.group(2) or "mm").lower()
        width_mm = round(raw_w * 25.4, 2) if u_w in ("in", "inch", "inches") else round(raw_w, 2)

    # Total Bobbin
    tb_m = re.search(r'(?:Total bobbin|Bobbin usage|Bobbin):\s*([\d,]+(?:\.\d+)?)\s*(m|ft|feet|yd|yards)?', full_text, re.I)
    total_bobbin_m = 0.0
    bobbin_unit = "m"
    raw_bobbin_str = ""
    if tb_m:
        raw_b = float(tb_m.group(1).replace(",", ""))
        unit_b = (tb_m.group(2) or "m").lower()
        bobbin_unit = unit_b
        raw_bobbin_str = f"{tb_m.group(1)}{tb_m.group(2) or ''}"
        if unit_b in ("ft", "feet"):
            total_bobbin_m = raw_b * FEET_TO_METERS
        elif unit_b in ("yd", "yards"):
            total_bobbin_m = raw_b * YARDS_TO_METERS
        else:
            total_bobbin_m = raw_b

    # Thread Usage (Total Thread)
    tu_m = re.search(r'(?:Thread usage|Total thread|Thread):\s*([\d,]+(?:\.\d+)?)\s*(m|ft|feet|yd|yards)?', full_text, re.I)
    total_thread_m = 0.0
    thread_unit = "m"
    raw_thread_str = ""
    if tu_m:
        raw_t = float(tu_m.group(1).replace(",", ""))
        unit_t = (tu_m.group(2) or "").lower()
        thread_unit = unit_t or "m"
        raw_thread_str = f"{tu_m.group(1)}{tu_m.group(2) or ''}"
        if unit_t in ("ft", "feet"):
            total_thread_m = raw_t * FEET_TO_METERS
        elif unit_t in ("yd", "yards"):
            total_thread_m = raw_t * YARDS_TO_METERS
        else:
            total_thread_m = raw_t

    # Detect if sheet is in feet
    sheet_is_feet = (thread_unit in ("ft", "feet")) or (bobbin_unit in ("ft", "feet"))

    # Auto-detect Repeat from design name, filename, and full sheet text (e.g. "[7 R]", "(7 R)", "Half R", "2 R")
    target_name = f"{design_name or ''} {clean_name}"
    repeat = extract_repeat_from_text(target_name)
    if repeat == 1.0 and full_text:
        repeat = extract_repeat_from_text(full_text)
    attrs = extract_part_attributes(target_name, repeat, width_mm)

    # Sequins Count
    seq_hdr = next((w for w in words if w["text"] == "Sequins:" and w["x0"] > 380), None)
    tu_hdr = next((w for w in words if w["text"] == "Thread" and w["x0"] > 380 and (not seq_hdr or w["top"] > seq_hdr["top"])), None)
    n_sharp = next((w for w in words if w["text"] == "N#" and w["x0"] > 350), None)

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

    # Thread Colors Table
    thread_colors = []
    if n_sharp:
        min_x = n_sharp["x0"] - 8
        th_words = [w for w in words if w["x0"] >= min_x and w["top"] > n_sharp["top"] and w["top"] < 780]
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
            m = re.search(r'^\s*(\d+)\.\s+(\S+)\s*(.*?)\s+([\d,]+(?:\.\d+)?)\s*(m|ft|feet|yd|yards)?(?:\s|$)', txt, re.I)
            if m:
                needle = int(m.group(1))
                raw_code = m.group(2).strip()
                raw_name = m.group(3).strip()
                raw_length = float(m.group(4).replace(",", ""))
                unit = (m.group(5) or "").lower()

                code, name, check_code = extract_dual_shade(raw_code, raw_name)

                # Auto-convert ft/yd to meters
                if unit in ("ft", "feet") or (not unit and sheet_is_feet):
                    length_m = raw_length * FEET_TO_METERS
                elif unit in ("yd", "yards"):
                    length_m = raw_length * YARDS_TO_METERS
                else:
                    length_m = raw_length

                tc_item = {
                    "needle": needle,
                    "code": code,
                    "name": name if name else code,
                    "length_m": round(length_m, 2),
                    "raw_length": raw_length,
                    "raw_unit": unit or ("ft" if sheet_is_feet else "m")
                }
                if check_code:
                    tc_item["check_code"] = check_code
                    tc_item["original_code"] = raw_code

                thread_colors.append(tc_item)
    else:
        # Fallback text regex
        for line_txt in full_text.splitlines():
            m = re.search(r'^\s*(\d+)\.\s+(\S+)\s*(.*?)\s+([\d,]+(?:\.\d+)?)\s*(m|ft|feet|yd|yards)?(?:\s|$)', line_txt, re.I)
            if m:
                needle = int(m.group(1))
                raw_code = m.group(2).strip()
                raw_name = m.group(3).strip()
                raw_length = float(m.group(4).replace(",", ""))
                unit = (m.group(5) or "").lower()

                code, name, check_code = extract_dual_shade(raw_code, raw_name)

                # Auto-convert ft/yd to meters
                if unit in ("ft", "feet") or (not unit and sheet_is_feet):
                    length_m = raw_length * FEET_TO_METERS
                elif unit in ("yd", "yards"):
                    length_m = raw_length * YARDS_TO_METERS
                else:
                    length_m = raw_length

                tc_item = {
                    "needle": needle,
                    "code": code,
                    "name": name if name else code,
                    "length_m": round(length_m, 2),
                    "raw_length": raw_length,
                    "raw_unit": unit or ("ft" if sheet_is_feet else "m")
                }
                if check_code:
                    tc_item["check_code"] = check_code
                    tc_item["original_code"] = raw_code

                thread_colors.append(tc_item)

    if total_thread_m == 0.0 and thread_colors:
        total_thread_m = round(sum(tc["length_m"] for tc in thread_colors), 2)

    return {
        "design_name": design_name,
        "stitches": stitches,
        "height_mm": height_mm,
        "width_mm": width_mm,
        "total_bobbin_m": round(total_bobbin_m, 2),
        "total_thread_m": round(total_thread_m, 2),
        "raw_thread_usage": raw_thread_str,
        "raw_bobbin_usage": raw_bobbin_str,
        "thread_unit": "ft" if sheet_is_feet else "m",
        "repeat": repeat,
        "is_double_repeat": attrs["is_double_repeat"],
        "size_tag": attrs["size_tag"],
        "tag_heads": attrs["tag_heads"],
        "is_size_split": attrs["is_size_split"],
        "is_multi_color_repeat": attrs["is_multi_color_repeat"],
        "sequins_total": sequins_total,
        "thread_colors": thread_colors
    }


def parse_wilcom_pdf(file_bytes: bytes, filename: str) -> list[dict]:
    """
    Parses a Wilcom production sheet PDF.
    Supports multi-page PDFs:
    - Multiple distinct design parts in a single PDF (e.g. Page 1 Front, Page 2 Bazzo, Page 3 Gala).
    - Thread list overflow onto Page 2 / 3 of the same part.
    Returns a list of structured part dictionaries.
    """
    clean_name = sanitize_filename(filename)

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        num_pages = len(pdf.pages)
        if num_pages == 0:
            raise ValueError("PDF file khali hai.")
        if num_pages > MAX_PDF_PAGES:
            raise ValueError(f"PDF mein {num_pages} pages hain (Limit: {MAX_PDF_PAGES}).")

        parts_list = []
        current_part = None

        for page_idx, page in enumerate(pdf.pages):
            pdata = _extract_page_data(page, clean_name, page_idx)

            # Determine if this page represents a new part or a continuation
            is_new_part = False
            if pdata["stitches"] > 0:
                if current_part is None:
                    is_new_part = True
                elif pdata["design_name"] and pdata["design_name"] != current_part["design_name"]:
                    is_new_part = True
                elif pdata["stitches"] != current_part["stitches"]:
                    is_new_part = True

            if is_new_part:
                if current_part is not None:
                    parts_list.append(current_part)

                p_name = pdata["design_name"] or f"{clean_name.replace('.pdf', '')}_P{page_idx+1}"
                current_part = {
                    "filename": f"{clean_name} (P{page_idx+1})" if num_pages > 1 else clean_name,
                    "design_name": p_name,
                    "repeat": pdata["repeat"],
                    "is_double_repeat": pdata.get("is_double_repeat", False),
                    "size_tag": pdata.get("size_tag"),
                    "tag_heads": pdata.get("tag_heads"),
                    "is_size_split": pdata.get("is_size_split", False),
                    "is_multi_color_repeat": pdata.get("is_multi_color_repeat", False),
                    "stitches": pdata["stitches"],
                    "height_mm": pdata["height_mm"],
                    "width_mm": pdata["width_mm"],
                    "total_bobbin_m": pdata["total_bobbin_m"],
                    "total_thread_m": pdata.get("total_thread_m", 0.0),
                    "raw_thread_usage": pdata.get("raw_thread_usage", ""),
                    "raw_bobbin_usage": pdata.get("raw_bobbin_usage", ""),
                    "thread_unit": pdata.get("thread_unit", "m"),
                    "sequins_total": pdata["sequins_total"],
                    "thread_colors": list(pdata["thread_colors"]),
                    "is_image": False,
                    "page_number": page_idx + 1
                }
            else:
                # Continuation page (thread overflow or additional page of same part)
                if current_part is not None:
                    existing_codes = {(tc["needle"], tc["code"]) for tc in current_part["thread_colors"]}
                    for tc in pdata["thread_colors"]:
                        if (tc["needle"], tc["code"]) not in existing_codes:
                            current_part["thread_colors"].append(tc)
                            existing_codes.add((tc["needle"], tc["code"]))

                    if pdata["total_bobbin_m"] > 0 and current_part["total_bobbin_m"] == 0:
                        current_part["total_bobbin_m"] = pdata["total_bobbin_m"]
                    if pdata.get("total_thread_m", 0) > 0 and current_part.get("total_thread_m", 0) == 0:
                        current_part["total_thread_m"] = pdata["total_thread_m"]
                    if pdata["sequins_total"] > 0 and current_part["sequins_total"] == 0:
                        current_part["sequins_total"] = pdata["sequins_total"]
                else:
                    p_name = pdata["design_name"] or f"{clean_name.replace('.pdf', '')}_P{page_idx+1}"
                    current_part = {
                        "filename": clean_name,
                        "design_name": p_name,
                        "repeat": pdata["repeat"],
                        "is_double_repeat": pdata.get("is_double_repeat", False),
                        "size_tag": pdata.get("size_tag"),
                        "tag_heads": pdata.get("tag_heads"),
                        "is_size_split": pdata.get("is_size_split", False),
                        "is_multi_color_repeat": pdata.get("is_multi_color_repeat", False),
                        "stitches": pdata["stitches"],
                        "height_mm": pdata["height_mm"],
                        "width_mm": pdata["width_mm"],
                        "total_bobbin_m": pdata["total_bobbin_m"],
                        "total_thread_m": pdata.get("total_thread_m", 0.0),
                        "raw_thread_usage": pdata.get("raw_thread_usage", ""),
                        "raw_bobbin_usage": pdata.get("raw_bobbin_usage", ""),
                        "thread_unit": pdata.get("thread_unit", "m"),
                        "sequins_total": pdata["sequins_total"],
                        "thread_colors": list(pdata["thread_colors"]),
                        "is_image": False,
                        "page_number": page_idx + 1
                    }

        if current_part is not None:
            parts_list.append(current_part)

        if not parts_list:
            raise ValueError("PDF se koi design ya stitches read nahi ho sakay.")

        return parts_list


def parse_image_part(file_bytes: bytes, filename: str) -> dict:
    """
    Parses an uploaded image safely and initializes a part entry.
    """
    clean_name = sanitize_filename(filename)
    Image.MAX_IMAGE_PIXELS = 30000000  # Safe limit against decompression bombs

    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img)  # Auto-orient based on mobile/camera EXIF
    width, height = img.size

    base_name = clean_name.rsplit(".", 1)[0]

    # Auto-detect Repeat & Width from filename if present (e.g. 'W450', '450mm', 'Width 420')
    repeat = extract_repeat_from_text(base_name)

    wm = re.search(r'\b(?:w|width)[_:\-\s]*([\d,]+(?:\.\d+)?)\s*(?:mm)?\b', base_name, re.I)
    if not wm:
        wm = re.search(r'([\d,]+(?:\.\d+)?)\s*mm\b', base_name, re.I)
    width_mm = float(wm.group(1).replace(",", "")) if wm else 0.0

    attrs = extract_part_attributes(base_name, repeat, width_mm)

    return {
        "filename": clean_name,
        "design_name": base_name,
        "repeat": repeat,
        "is_double_repeat": attrs["is_double_repeat"],
        "size_tag": attrs["size_tag"],
        "tag_heads": attrs["tag_heads"],
        "is_size_split": attrs["is_size_split"],
        "is_multi_color_repeat": attrs["is_multi_color_repeat"],
        "stitches": 120000,  # sensible default for manual review
        "height_mm": 0.0,
        "width_mm": width_mm,
        "total_bobbin_m": 150.0,
        "total_thread_m": 570.0,
        "raw_thread_usage": "570.0m",
        "thread_unit": "m",
        "sequins_total": 0,
        "thread_colors": [
            {"needle": 1, "code": "same", "name": "same (Base Match)", "length_m": 450.0},
            {"needle": 2, "code": "3357", "name": "Golden Zari", "length_m": 120.0}
        ],
        "is_image": True,
        "image_bytes": file_bytes,
        "image_size": (width, height)
    }
