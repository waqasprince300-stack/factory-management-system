"""
Configuration and Defaults for Threadworks Embroidery Calculator.
"""

# Security & Upload Constraints
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB max per file
MAX_PDF_PAGES = 25
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

# Production Defaults
DEFAULT_MACHINE_HEADS = 28
DEFAULT_BASE_COLORS = 6
DEFAULT_LOTS_COUNT = 1.0

# Wastage Default: Auto ZERO (0.0%), user can adjust
DEFAULT_WASTAGE_PCT = 0.0

# Thread & Cone Defaults: 2770 Meters (Standard factory cone)
DEFAULT_CONE_UNIT = "Meters (m)"
DEFAULT_CONE_CAPACITY_METERS = 2770.0
DEFAULT_CONE_CAPACITY_YARDS = 3000.0

# Financials Defaults
DEFAULT_STITCH_RATE = 0.45  # PKR per 1,000 stitches
DEFAULT_CONE_PRICE = 280.0  # PKR per cone
DEFAULT_BOBBIN_RATE_PER_METER = 320.0 / 10000.0  # approx PKR per meter

# Machine Timing Defaults
DEFAULT_MACHINE_RPM = 750
DEFAULT_EFFICIENCY = 0.80  # 80% realistic factory efficiency
DEFAULT_SHIFT_HOURS = 8.0

# Unit Conversion Constants
YARDS_TO_METERS = 0.9144
METERS_TO_YARDS = 1.0936133
