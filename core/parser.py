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
from core.config import MAX_PDF_PAGES
from core.security import sanitize_filename


def extract_part_attributes(name: str, repeat: float = 1.0) -> dict:
    """
    Extracts size split, multi-color head tags, and double repeat flags from design/file name:
    - Multi-color repeat: e.g. '(9 H)', '(4 Head)' -> tag_heads=9/4, is_multi_color_repeat=True
    - Size split: e.g. '(S)', '(M)', '(L)' -> size_tag='S'/'M'/'L', is_size_split=True, is_double_repeat=True
    - Double repeat: 2 R, 14H, 15H, 'double', or size split
    """
    target = str(name or "")

    # 1. Size split in brackets: (S), (M), (L)
    size_m = re.search(r'\(\s*([sml])\s*\)', target, re.I)
    size_tag = size_m.group(1).upper() if size_m else None

    # 2. Head tag in brackets or word: (9 H), (9 Head), (4 H), (4 Head), 9H, 4H
    head_m = re.search(r'\(\s*(\d+)\s*(?:h|head|heads)\b', target, re.I)
    if not head_m:
        head_m = re.search(r'\b(\d+)\s*(?:h|head|heads)\b', target, re.I)
    tag_heads = int(head_m.group(1)) if head_m else None

    is_size_split = bool(size_tag)
    # Multi-color repeat tag: heads between 2 and 12 (not half heads 14/15)
    is_multi_color_repeat = bool(tag_heads and tag_heads in range(2, 13) and not is_size_split)

    # Double repeat: 2 R, 14H, 15H, 'double', or size split (S, M, L)
    is_double_repeat = (
        (repeat >= 2.0) or
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

    # Dimensions
    hm = re.search(r'Height:\s*([\d\.]+)\s*mm', full_text)
    height_mm = float(hm.group(1)) if hm else 0.0
    wm = re.search(r'Width:\s*([\d\.]+)\s*mm', full_text)
    width_mm = float(wm.group(1)) if wm else 0.0

    # Total Bobbin
    tb_m = re.search(r'Total bobbin:\s*([\d\.]+)\s*(m|ft)', full_text, re.I)
    total_bobbin_m = float(tb_m.group(1)) if tb_m else 0.0
    if tb_m and tb_m.group(2).lower() in ("ft", "feet"):
        total_bobbin_m *= 0.3048

    # Auto-detect Repeat (e.g. "1 R", "Half R", "2 R", "Double R", "Double Repeat")
    target_name = f"{design_name or ''} {clean_name}"
    repeat = 1.0
    rep_m = re.search(r'\(\s*(\d+(?:\.\d+)?|\bhalf\b|\bdouble\b)?\s*(?:\+?\s*(half|double))?\s*r(?:epeat)?\s*\)', target_name, re.I)
    if rep_m:
        p1 = rep_m.group(1) or ""
        p2 = rep_m.group(2) or ""
        r_val = 0.0
        if p1.lower() == "half":
            r_val += 0.5
        elif p1.lower() == "double":
            r_val += 2.0
        elif p1:
            try:
                r_val += float(p1)
            except ValueError:
                pass
        if p2.lower() == "half":
            r_val += 0.5
        elif p2.lower() == "double":
            r_val += 2.0
        if r_val > 0:
            repeat = r_val
    elif re.search(r'\bdouble\s*repeat\b', target_name, re.I):
        repeat = 2.0

    attrs = extract_part_attributes(target_name, repeat)

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
    else:
        # Fallback text regex
        for line_txt in full_text.splitlines():
            m = re.search(r'^\s*(\d+)\.\s+(\S+)\s*(.*?)\s+([\d,]+(?:\.\d+)?)\s*(m|ft)', line_txt, re.I)
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
        "design_name": design_name,
        "stitches": stitches,
        "height_mm": height_mm,
        "width_mm": width_mm,
        "total_bobbin_m": round(total_bobbin_m, 2),
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

    # Auto-detect Repeat from filename if present
    repeat = 1.0
    rep_m = re.search(r'\(\s*(\d+(?:\.\d+)?|\bhalf\b|\bdouble\b)?\s*(?:\+?\s*(half|double))?\s*r(?:epeat)?\s*\)', base_name, re.I)
    if rep_m:
        p1 = rep_m.group(1) or ""
        p2 = rep_m.group(2) or ""
        r_val = 0.0
        if p1.lower() == "half":
            r_val += 0.5
        elif p1.lower() == "double":
            r_val += 2.0
        elif p1:
            try:
                r_val += float(p1)
            except ValueError:
                pass
        if p2.lower() == "half":
            r_val += 0.5
        elif p2.lower() == "double":
            r_val += 2.0
        if r_val > 0:
            repeat = r_val
    elif re.search(r'\bdouble\s*repeat\b', base_name, re.I):
        repeat = 2.0

    attrs = extract_part_attributes(base_name, repeat)

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
        "width_mm": 0.0,
        "total_bobbin_m": 150.0,
        "sequins_total": 0,
        "thread_colors": [
            {"needle": 1, "code": "same", "name": "same (Base Match)", "length_m": 450.0},
            {"needle": 2, "code": "3357", "name": "Golden Zari", "length_m": 120.0}
        ],
        "is_image": True,
        "image_bytes": file_bytes,
        "image_size": (width, height)
    }
