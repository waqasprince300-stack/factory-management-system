"""
Configuration and Defaults for Threadworks Embroidery Calculator.
Industrial Multi-Head Production Constants.
"""

# Security & Upload Constraints
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024  # 25 MB max per file
MAX_PDF_PAGES = 25
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}

# Production Defaults (Standard Pakistani Multi-head flat machines)
DEFAULT_MACHINE_HEADS = 30
DEFAULT_BASE_COLORS = 6
DEFAULT_LOTS_COUNT = 1.0

# Wastage Default: Auto ZERO (0.0%), user can adjust
DEFAULT_WASTAGE_PCT = 0.0

# Thread & Cone Defaults: 2700 Meters (Standard factory cone)
DEFAULT_CONE_UNIT = "Meters"
DEFAULT_CONE_CAPACITY_METERS = 2700.0
DEFAULT_CONE_CAPACITY_YARDS = 3000.0

# Financials Defaults (PKR)
DEFAULT_STITCH_RATE = 1.0  # PKR per 1,000 stitches
DEFAULT_CONE_PRICE = 220.0  # PKR per cone
DEFAULT_BOBBIN_CONE_PRICE = 320.0  # PKR per bobbin cone (10,000m)
DEFAULT_BOBBIN_RATE_PER_METER = 320.0 / 10000.0  # approx PKR per meter

# Backing Material (Bukram / Paper / Tarpin)
DEFAULT_HEAD_PITCH_MM = 300.0  # Standard 300mm / 30cm head distance
DEFAULT_FRAME_MARGIN_METERS = 0.5  # Extra cloth/bukram margin per frame
DEFAULT_BUKRAM_ROLL_METERS = 100.0  # Standard 100 meter roll
DEFAULT_BUKRAM_ROLL_PRICE = 1800.0  # PKR per roll

# Bobbin Usage Rule: 1 Million Stitches ≈ 160 grams bobbin thread
DEFAULT_BOBBIN_GRAMS_PER_MILLION_STITCHES = 160.0

# Machine Timing Defaults (Real Factory Operations)
DEFAULT_MACHINE_RPM = 750  # Machine top speed
DEFAULT_EFFICIENCY = 0.80  # 80% realistic factory efficiency
DEFAULT_REAL_RPM = 680  # Real average speed factoring long stitches & slow-downs
DEFAULT_COLOR_CHANGE_SECONDS = 10.0  # Machine pause per color change
DEFAULT_FRAME_CHANGE_MINUTES = 12.0  # Takaai & frame loading time per repeat
DEFAULT_SHIFT_HOURS = 12.0  # Standard 12-hour factory shifts (2 shifts/day)

# Unit Conversion Constants
FEET_TO_METERS = 0.3048
METERS_TO_FEET = 3.280839895
YARDS_TO_METERS = 0.9144
METERS_TO_YARDS = 1.093613298

# Double Head Frame Threshold (Designs wider than 450mm auto-switch to Half Head / Double Head)
DOUBLE_HEAD_WIDTH_THRESHOLD_MM = 450.0
