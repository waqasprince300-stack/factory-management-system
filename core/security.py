"""
Security, validation, and sanitization utilities.
Protects the app from oversized files, corrupted payloads, and injection attacks.
"""

import os
import re
from core.config import MAX_FILE_SIZE_BYTES, ALLOWED_EXTENSIONS


def sanitize_filename(filename: str) -> str:
    """
    Strips directory traversal, null bytes, and dangerous characters from filenames.
    """
    clean = os.path.basename(filename)
    # Remove null bytes and non-printable characters
    clean = re.sub(r'[\x00-\x1f\x7f]', '', clean)
    # Limit length
    clean = clean.strip()[:120]
    return clean if clean else "unnamed_part"


def validate_uploaded_file(file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """
    Validates file size, extension, and magic signature.
    Returns (is_valid, error_message).
    """
    if len(file_bytes) == 0:
        return False, "File khali hai (0 bytes)."

    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        return False, f"File ka size 25 MB se ziada hai ({len(file_bytes) / (1024*1024):.1f} MB)."

    ext = os.path.splitext(filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Yeh file format ({ext}) allowed nahi hai. Sirf PDF ya Image (PNG, JPG, WEBP) chalay gi."

    # Magic byte checks
    if ext == ".pdf":
        if not file_bytes.startswith(b"%PDF-"):
            return False, "File PDF format ke standard header se match nahi kar rahi."
    elif ext in {".png"}:
        if not file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return False, "Corrupted PNG image file."
    elif ext in {".jpg", ".jpeg"}:
        if not file_bytes.startswith(b"\xff\xd8\xff"):
            return False, "Corrupted JPEG image file."

    return True, ""


def clamp_numeric(val: float, min_val: float, max_val: float, default_val: float) -> float:
    """
    Safely clamps a numeric value within acceptable bounds.
    """
    try:
        f = float(val)
        if f < min_val:
            return min_val
        if f > max_val:
            return max_val
        return f
    except (ValueError, TypeError):
        return default_val
