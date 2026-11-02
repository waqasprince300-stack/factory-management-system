"""
PDF Report Generator for Threadworks Embroidery ERP
Generates professional A4 Factory Production Job Card & Dhaaga Requisition Slip.
"""

import io
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_job_card_pdf(
    design_name: str,
    num_pieces: int,
    lots_count: float,
    machine_heads: int,
    base_colors_count: int,
    suits_per_base_color: int,
    total_suit_stitches: int,
    stitch_rate: float,
    piece_rate: float,
    total_order_amount: float,
    cone_capacity_val: float,
    cone_unit: str,
    waste_pct: float,
    shifts_needed: int,
    days_needed: float,
    total_runs: int,
    parts_data: list[dict],
    cones_data: list[dict],
    total_order_cones: int,
    bobbin_data: dict = None
) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=28,
        leftMargin=28,
        topMargin=26,
        bottomMargin=26
    )

    styles = getSampleStyleSheet()

    # Typography
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=19,
        textColor=colors.HexColor('#0f172a'),
        alignment=1
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#d97706'),
        alignment=1
    )

    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#334155')
    )

    bold_meta = ParagraphStyle(
        'BoldMeta',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor('#0f172a')
    )

    section_hdr = ParagraphStyle(
        'SecHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#0f172a')
    )

    table_header = ParagraphStyle(
        'THeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white
    )

    table_body = ParagraphStyle(
        'TBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#1e293b')
    )

    table_body_bold = ParagraphStyle(
        'TBodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#0f172a')
    )

    elements = []

    # Title & Subtitle Banner
    elements.append(Paragraph("THREADWORKS EMBROIDERY FACTORY", title_style))
    elements.append(Paragraph("FACTORY PRODUCTION JOB CARD & DHAAGA REQUISITION", subtitle_style))
    elements.append(Spacer(1, 8))

    # Order Meta Table (3 columns x 3 rows)
    info_data = [
        [
            Paragraph(f"<b>Design / Suit:</b> {design_name}", bold_meta),
            Paragraph(f"<b>Order Qty:</b> {num_pieces} Suits ({lots_count:g} Lots)", bold_meta),
            Paragraph(f"<b>Machine:</b> {machine_heads} Heads", bold_meta)
        ],
        [
            Paragraph(f"<b>Base Shades:</b> {base_colors_count} ({suits_per_base_color} pcs/clr)", meta_style),
            Paragraph(f"<b>1 Suit Stitches:</b> {total_suit_stitches:,} st", meta_style),
            Paragraph(f"<b>1 Piece Rate:</b> Rs {piece_rate:,.2f}", bold_meta)
        ],
        [
            Paragraph(f"<b>Stitch Rate:</b> Rs {stitch_rate:.2f} / 1k st", meta_style),
            Paragraph(f"<b>Total Order Bill:</b> Rs {total_order_amount:,.0f}", bold_meta),
            Paragraph(f"<b>Cone Size:</b> {cone_capacity_val:,.0f} {cone_unit} ({waste_pct:.0f}% waste)", meta_style)
        ]
    ]
    info_table = Table(info_data, colWidths=[180, 185, 174])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#f8fafc')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 7),
        ('RIGHTPADDING', (0,0), (-1,-1), 7),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 9))

    # Suit Parts Section
    elements.append(Paragraph("<b>SUIT PARTS CUT-SHEET & HEADING BREAKDOWN</b>", section_hdr))
    elements.append(Spacer(1, 3))
    parts_header = [
        Paragraph("Part Name", table_header),
        Paragraph("Setting / Head Mode", table_header),
        Paragraph("Wilcom St", table_header),
        Paragraph("Repeat", table_header),
        Paragraph("1 Suit Stitches", table_header),
        Paragraph("Rate (PKR)", table_header)
    ]
    p_rows = [parts_header]
    for p in parts_data:
        p_rows.append([
            Paragraph(str(p.get("name", "")), table_body_bold),
            Paragraph(str(p.get("setting", "")), table_body),
            Paragraph(f"{int(p.get('wilcom_st', 0)):,}", table_body),
            Paragraph(f"{float(p.get('repeat', 1.0)):g}", table_body),
            Paragraph(f"{int(p.get('suit_st', 0)):,}", table_body_bold),
            Paragraph(f"Rs {float(p.get('rate', 0.0)):,.2f}", table_body_bold)
        ])

    p_table = Table(p_rows, colWidths=[165, 134, 60, 45, 75, 60])
    p_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(p_table)
    elements.append(Spacer(1, 9))

    # Dhaaga Requisition Table
    elements.append(Paragraph("<b>DHAAGA (CONES) REQUISITION — STORE ISSUE LIST</b>", section_hdr))
    elements.append(Spacer(1, 3))
    dhaaga_header = [
        Paragraph("Needle #", table_header),
        Paragraph("Color Code", table_header),
        Paragraph("Color Description / Check Shirt", table_header),
        Paragraph("Type", table_header),
        Paragraph("1 Suit (m)", table_header),
        Paragraph("Kul Cones", table_header)
    ]
    d_rows = [dhaaga_header]
    for d in cones_data:
        d_rows.append([
            Paragraph(f"N# {d.get('needle', '')}", table_body),
            Paragraph(str(d.get('code', '')), table_body_bold),
            Paragraph(str(d.get('desc', '')), table_body),
            Paragraph(str(d.get('type', '')), table_body),
            Paragraph(f"{float(d.get('suit_m', 0.0)):,.1f}m", table_body),
            Paragraph(f"<b>{d.get('cones', 0)} Cones</b>", table_body_bold)
        ])

    d_table = Table(d_rows, colWidths=[52, 75, 172, 85, 65, 90])
    d_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#d97706')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#cbd5e1')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#fef3c7')]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    elements.append(d_table)
    elements.append(Spacer(1, 7))

    # Bobbin / Khicha & Summary Bar
    bobbin_txt = ""
    if bobbin_data:
        b_clr = bobbin_data.get("color", "White")
        b_cones = bobbin_data.get("cones", 0)
        b_meters = bobbin_data.get("meters", 0.0)
        bobbin_txt = f" | <b>Bobbin (Khicha - {b_clr}):</b> {b_cones} Cones ({b_meters:,.0f}m)"

    summary_text = f"<b>KUL DHAAGA CONES: {total_order_cones} Cones</b>{bobbin_txt} | <b>Total Repeats:</b> {total_runs} R | <b>Est:</b> ~{shifts_needed} Shifts ({days_needed} Din)"
    cones_summary = Table(
        [[
            Paragraph(summary_text, ParagraphStyle('KCS', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, textColor=colors.HexColor('#92400e')))
        ]],
        colWidths=[539]
    )
    cones_summary.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#fef3c7')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#f59e0b')),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(cones_summary)
    elements.append(Spacer(1, 14))

    # Signatures Table (KeepTogether so it doesn't break onto a 2nd page)
    sig_data = [
        [
            Paragraph("<b>Master Signature:</b> ____________________", meta_style),
            Paragraph("<b>Store Incharge:</b> ____________________", meta_style),
            Paragraph("<b>Gate / Delivery:</b> ____________________", meta_style)
        ]
    ]
    sig_table = Table(sig_data, colWidths=[180, 180, 179])
    sig_table.setStyle(TableStyle([
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(KeepTogether(sig_table))

    doc.build(elements)
    return buffer.getvalue()

