"""
Pre-configured Wilcom Production Demo Data (ZB-1149 Multi-Part Suit)
Used as default state so the user never encounters a blank screen.
"""

def get_demo_parts(default_heads: int = 28):
    """
    Returns the 5 standard production cut parts for ZB-1149 design.
    Matches factory Wilcom production worksheet data.
    """
    return {
        "demo_front": {
            "filename": "ZB-1149-FRONT PANEL (1 R).pdf",
            "design_name": "ZB-1149-FRONT PANEL",
            "repeat": 1.0,
            "heads": default_heads,
            "stitches": 206345,
            "height_mm": 950.0,
            "width_mm": 420.0,
            "total_bobbin_m": 412.0,
            "sequins_total": 0,
            "thread_colors": [
                {"needle": 1, "code": "same", "name": "same", "length_m": 659.44},
                {"needle": 2, "code": "3357", "name": "Golden Gliter", "length_m": 53.9},
                {"needle": 3, "code": "3119", "name": "3119", "length_m": 33.35},
                {"needle": 4, "code": "1019", "name": "1019", "length_m": 25.28},
                {"needle": 5, "code": "1181", "name": "1181", "length_m": 27.63},
                {"needle": 7, "code": "1123", "name": "1123", "length_m": 383.38}
            ],
            "is_image": False
        },
        "demo_bazzo": {
            "filename": "ZB-1149-BAZZO (1 R).pdf",
            "design_name": "ZB-1149-BAZZO",
            "repeat": 1.0,
            "heads": default_heads,
            "stitches": 100313,
            "height_mm": 520.0,
            "width_mm": 380.0,
            "total_bobbin_m": 195.0,
            "sequins_total": 0,
            "thread_colors": [
                {"needle": 1, "code": "same", "name": "same", "length_m": 302.97},
                {"needle": 2, "code": "3357", "name": "Golden Gliter", "length_m": 35.99},
                {"needle": 7, "code": "1123", "name": "1123", "length_m": 184.97}
            ],
            "is_image": False
        },
        "demo_kali_l": {
            "filename": "ZB-1149-LEFT KALI (1 R).pdf",
            "design_name": "ZB-1149-LEFT KALI",
            "repeat": 1.0,
            "heads": default_heads,
            "stitches": 66429,
            "height_mm": 950.0,
            "width_mm": 180.0,
            "total_bobbin_m": 128.0,
            "sequins_total": 0,
            "thread_colors": [
                {"needle": 1, "code": "same", "name": "same", "length_m": 163.93},
                {"needle": 2, "code": "3357", "name": "Golden Gliter", "length_m": 29.93},
                {"needle": 3, "code": "3119", "name": "3119", "length_m": 17.09},
                {"needle": 4, "code": "1019", "name": "1019", "length_m": 12.94},
                {"needle": 5, "code": "1181", "name": "1181", "length_m": 12.69},
                {"needle": 7, "code": "1123", "name": "1123", "length_m": 146.52}
            ],
            "is_image": False
        },
        "demo_kali_r": {
            "filename": "ZB-1149-RIGHT KALI (1 R).pdf",
            "design_name": "ZB-1149-RIGHT KALI",
            "repeat": 1.0,
            "heads": default_heads,
            "stitches": 66555,
            "height_mm": 950.0,
            "width_mm": 180.0,
            "total_bobbin_m": 128.0,
            "sequins_total": 0,
            "thread_colors": [
                {"needle": 1, "code": "same", "name": "same", "length_m": 163.93},
                {"needle": 2, "code": "3357", "name": "Golden Gliter", "length_m": 30.07},
                {"needle": 3, "code": "3119", "name": "3119", "length_m": 17.13},
                {"needle": 4, "code": "1019", "name": "1019", "length_m": 13.02},
                {"needle": 5, "code": "1181", "name": "1181", "length_m": 12.69},
                {"needle": 7, "code": "1123", "name": "1123", "length_m": 146.58}
            ],
            "is_image": False
        },
        "demo_organza": {
            "filename": "ZB-1149-BAZZO+FRONT PATTI2 (Half R) Organza.pdf",
            "design_name": "ZB-1149-ORGANZA PATTI",
            "repeat": 0.5,
            "heads": default_heads,
            "stitches": 217736,
            "height_mm": 950.0,
            "width_mm": 420.0,
            "total_bobbin_m": 380.0,
            "sequins_total": 0,
            "thread_colors": [
                {"needle": 1, "code": "same", "name": "same", "length_m": 686.94},
                {"needle": 2, "code": "3357", "name": "Golden Gliter", "length_m": 68.61},
                {"needle": 3, "code": "3119", "name": "3119", "length_m": 41.94},
                {"needle": 4, "code": "1019", "name": "1019", "length_m": 44.35},
                {"needle": 5, "code": "1181", "name": "1181", "length_m": 39.31},
                {"needle": 7, "code": "1123", "name": "1123", "length_m": 414.68}
            ],
            "is_image": False
        }
    }
