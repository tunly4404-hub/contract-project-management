import os
import requests
import io
from datetime import date, datetime
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONTS_DIR = "fonts"
REGULAR_FONT_PATH = os.path.join(FONTS_DIR, "NotoSansThai-Regular.ttf")
BOLD_FONT_PATH = os.path.join(FONTS_DIR, "NotoSansThai-Bold.ttf")

def download_fonts_if_needed():
    if not os.path.exists(FONTS_DIR):
        os.makedirs(FONTS_DIR)
        
    # Standard Noto Sans Thai from Google Fonts Git repo
    if not os.path.exists(REGULAR_FONT_PATH):
        print("Downloading NotoSansThai-Regular.ttf...")
        url = "https://github.com/google/fonts/raw/main/ofl/notosansthai/NotoSansThai-Regular.ttf"
        r = requests.get(url, timeout=15)
        with open(REGULAR_FONT_PATH, "wb") as f:
            f.write(r.content)
            
    if not os.path.exists(BOLD_FONT_PATH):
        print("Downloading NotoSansThai-Bold.ttf...")
        url = "https://github.com/google/fonts/raw/main/ofl/notosansthai/NotoSansThai-Bold.ttf"
        r = requests.get(url, timeout=15)
        with open(BOLD_FONT_PATH, "wb") as f:
            f.write(r.content)

try:
    download_fonts_if_needed()
    pdfmetrics.registerFont(TTFont('NotoSansThai', REGULAR_FONT_PATH))
    pdfmetrics.registerFont(TTFont('NotoSansThai-Bold', BOLD_FONT_PATH))
    
    # Register font family mapping in both original case and lowercase
    # ReportLab uses lowercase names internally for family lookup.
    pdfmetrics.registerFontFamily(
        'NotoSansThai',
        normal='NotoSansThai',
        bold='NotoSansThai-Bold',
        italic='NotoSansThai',
        boldItalic='NotoSansThai-Bold'
    )
    pdfmetrics.registerFontFamily(
        'notosansthai',
        normal='NotoSansThai',
        bold='NotoSansThai-Bold',
        italic='NotoSansThai',
        boldItalic='NotoSansThai-Bold'
    )
    pdfmetrics.registerFontFamily(
        'notosansthai-bold',
        normal='NotoSansThai-Bold',
        bold='NotoSansThai-Bold',
        italic='NotoSansThai-Bold',
        boldItalic='NotoSansThai-Bold'
    )
except Exception as e:
    print(f"Warning: Failed to load Thai fonts: {e}")

# Styles Setup
styles = getSampleStyleSheet()

THAI_NORMAL = ParagraphStyle(
    'ThaiNormal',
    parent=styles['Normal'],
    fontName='NotoSansThai',
    fontSize=9,
    leading=13,
    textColor=colors.HexColor('#334155')
)

THAI_BOLD = ParagraphStyle(
    'ThaiBold',
    parent=THAI_NORMAL,
    fontName='NotoSansThai',
    textColor=colors.HexColor('#1e293b')
)

THAI_CENTER = ParagraphStyle(
    'ThaiCenter',
    parent=THAI_NORMAL,
    alignment=1
)

THAI_RIGHT = ParagraphStyle(
    'ThaiRight',
    parent=THAI_NORMAL,
    alignment=2
)

TITLE_STYLE = ParagraphStyle(
    'TitleStyle',
    parent=THAI_NORMAL,
    fontName='NotoSansThai',
    fontSize=18,
    leading=24,
    textColor=colors.HexColor('#1e293b')
)

SUBTITLE_STYLE = ParagraphStyle(
    'SubtitleStyle',
    parent=THAI_NORMAL,
    fontSize=10,
    leading=14,
    textColor=colors.HexColor('#64748b')
)

HEADER_STYLE = ParagraphStyle(
    'HeaderStyle',
    parent=THAI_NORMAL,
    fontName='NotoSansThai',
    textColor=colors.white,
    alignment=1
)

def format_thai_date(d):
    if not d:
        return "-"
    if isinstance(d, (date, datetime)):
        months = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
        return f"{d.day} {months[d.month-1]} {d.year + 543}"
    return str(d)

def format_currency(val):
    if val is None:
        return "฿0.00"
    return f"฿{val:,.2f}"

def export_projects_to_pdf(projects):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )
    
    story = []
    
    # Title
    story.append(Paragraph("<b>รายงานสรุปภาพรวมโครงการสัญญาและงบประมาณ</b>", TITLE_STYLE))
    story.append(Paragraph(f"พิมพ์ ณ วันที่: {format_thai_date(date.today())}", SUBTITLE_STYLE))
    story.append(Spacer(1, 15))
    
    # Table Headers
    headers = [
        Paragraph("<b>ลำดับ</b>", HEADER_STYLE),
        Paragraph("<b>ชื่อโครงการ / หน่วยงานผู้ว่าจ้าง</b>", HEADER_STYLE),
        Paragraph("<b>บริษัทที่รับผิดชอบ / ประเภทงาน</b>", HEADER_STYLE),
        Paragraph("<b>ปีงบประมาณ</b>", HEADER_STYLE),
        Paragraph("<b>งบประมาณ (บาท)</b>", HEADER_STYLE),
        Paragraph("<b>สถานะ</b>", HEADER_STYLE)
    ]
    
    data = [headers]
    
    total_budget = 0.0
    for idx, p in enumerate(projects, 1):
        total_budget += p.budget or 0.0
        
        name_p = Paragraph(f"<b>{p.name}</b><br/><font color='#64748b'>ผู้ว่าจ้าง: {p.owner}</font>", THAI_NORMAL)
        contractor_p = Paragraph(f"{p.contractor or '-'}<br/><font color='#64748b'>{p.job_type or '-'}</font>", THAI_NORMAL)
        fiscal_p = Paragraph(str(p.fiscal_year) if p.fiscal_year else "-", THAI_CENTER)
        budget_p = Paragraph(format_currency(p.budget), THAI_RIGHT)
        
        status_color = "#3b82f6" # blue
        if p.status == "ล่าช้า":
            status_color = "#f43f5e" # rose
        elif p.status == "ส่งมอบแล้ว":
            status_color = "#10b981" # emerald
            
        status_p = Paragraph(f"<font color='{status_color}'><b>{p.status}</b></font>", THAI_CENTER)
        
        data.append([
            Paragraph(str(idx), THAI_CENTER),
            name_p,
            contractor_p,
            fiscal_p,
            budget_p,
            status_p
        ])
        
    # Summary Row
    data.append([
        Paragraph("<b>รวมทั้งสิ้น</b>", THAI_CENTER),
        Paragraph(f"<b>{len(projects)} โครงการ</b>", THAI_NORMAL),
        "", "",
        Paragraph(f"<b>{format_currency(total_budget)}</b>", THAI_RIGHT),
        ""
    ])
    
    # Define widths (Sum of widths = 555 for A4 Portrait with margins)
    col_widths = [30, 185, 150, 50, 85, 55]
    
    t = Table(data, colWidths=col_widths, repeatRows=1)
    
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')), # Indigo header
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#cbd5e1')),
        ('SPAN', (1, -1), (3, -1)), # span 'โครงการ'
        ('SPAN', (4, -1), (5, -1)), # span budget sum
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#4f46e5')),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#4f46e5')),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ])
    
    # Alternating row colors
    for r in range(1, len(data) - 1):
        if r % 2 == 0:
            t_style.add('BACKGROUND', (0, r), (-1, r), colors.HexColor('#f8fafc'))
            
    t.setStyle(t_style)
    story.append(t)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def export_purchase_orders_to_pdf(pos):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )
    
    story = []
    
    story.append(Paragraph("<b>รายงานสรุปรายการใบสั่งซื้อวัสดุ (Purchase Orders)</b>", TITLE_STYLE))
    story.append(Paragraph(f"พิมพ์ ณ วันที่: {format_thai_date(date.today())}", SUBTITLE_STYLE))
    story.append(Spacer(1, 15))
    
    headers = [
        Paragraph("<b>ลำดับ</b>", HEADER_STYLE),
        Paragraph("<b>เลขที่ PO / ชื่อโครงการอ้างอิง</b>", HEADER_STYLE),
        Paragraph("<b>รายการวัสดุ / ผู้จัดซื้อ</b>", HEADER_STYLE),
        Paragraph("<b>งบประมาณ (บาท)</b>", HEADER_STYLE),
        Paragraph("<b>กำหนดวันส่งมอบ</b>", HEADER_STYLE),
        Paragraph("<b>สถานะ</b>", HEADER_STYLE)
    ]
    
    data = [headers]
    
    total_budget = 0.0
    for idx, po in enumerate(pos, 1):
        total_budget += po.budget or 0.0
        
        proj_name = po.project.name if po.project else "-"
        po_info = Paragraph(f"<b>{po.po_number}</b><br/><font color='#64748b'>โครงการ: {proj_name}</font>", THAI_NORMAL)
        material_info = Paragraph(f"<b>{po.material_type}</b><br/><font color='#64748b'>{po.contractor}</font>", THAI_NORMAL)
        budget_p = Paragraph(format_currency(po.budget), THAI_RIGHT)
        due_p = Paragraph(format_thai_date(po.due_date), THAI_CENTER)
        
        status_color = "#f43f5e" # red (not sent)
        if po.delivery_status == "ส่งมอบแล้ว":
            status_color = "#10b981" # emerald
            
        status_p = Paragraph(f"<font color='{status_color}'><b>{po.delivery_status}</b></font>", THAI_CENTER)
        
        data.append([
            Paragraph(str(idx), THAI_CENTER),
            po_info,
            material_info,
            budget_p,
            due_p,
            status_p
        ])
        
    data.append([
        Paragraph("<b>รวมทั้งสิ้น</b>", THAI_CENTER),
        Paragraph(f"<b>{len(pos)} รายการ PO</b>", THAI_NORMAL),
        "",
        Paragraph(f"<b>{format_currency(total_budget)}</b>", THAI_RIGHT),
        "", ""
    ])
    
    col_widths = [30, 185, 140, 85, 65, 50]
    
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0284c7')), # Sky Blue header
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#cbd5e1')),
        ('SPAN', (1, -1), (2, -1)),
        ('SPAN', (3, -1), (5, -1)),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#0284c7')),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#0284c7')),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ])
    
    for r in range(1, len(data) - 1):
        if r % 2 == 0:
            t_style.add('BACKGROUND', (0, r), (-1, r), colors.HexColor('#f8fafc'))
            
    t.setStyle(t_style)
    story.append(t)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def export_project_detail_to_pdf(project):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )
    
    story = []
    
    # Document Header
    story.append(Paragraph(f"<b>รายงานรายละเอียดโครงการ: {project.name}</b>", TITLE_STYLE))
    story.append(Paragraph(f"พิมพ์ ณ วันที่: {format_thai_date(date.today())} | ออกโดยระบบบริหารจัดการสัญญาโครงการ", SUBTITLE_STYLE))
    story.append(Spacer(1, 15))
    
    # Section 1: General Info Block
    story.append(Paragraph("<b>1. ข้อมูลรายละเอียดสัญญาและหน่วยงาน</b>", THAI_BOLD))
    story.append(Spacer(1, 5))
    
    info_data = [
        [Paragraph("<b>เลขที่โครงการสัญญา:</b>", THAI_BOLD), Paragraph(project.contract_number or "-", THAI_NORMAL),
         Paragraph("<b>ชื่อโครงการสัญญา:</b>", THAI_BOLD), Paragraph(project.name, THAI_NORMAL)],
        [Paragraph("<b>หน่วยงานผู้ว่าจ้าง:</b>", THAI_BOLD), Paragraph(project.owner, THAI_NORMAL),
         Paragraph("<b>บริษัทผู้รับผิดชอบ:</b>", THAI_BOLD), Paragraph(project.contractor or "-", THAI_NORMAL)],
        [Paragraph("<b>ประเภทงาน:</b>", THAI_BOLD), Paragraph(project.job_type or "-", THAI_NORMAL),
         Paragraph("<b>ปีงบประมาณ:</b>", THAI_BOLD), Paragraph(str(project.fiscal_year) if project.fiscal_year else "-", THAI_NORMAL)],
        [Paragraph("<b>งบประมาณโครงการ:</b>", THAI_BOLD), Paragraph(format_currency(project.budget), THAI_NORMAL),
         Paragraph("<b>ระยะเวลาสัญญา (วัน):</b>", THAI_BOLD), Paragraph(f"{project.contract_duration_days} วัน" if project.contract_duration_days else "-", THAI_NORMAL)],
        [Paragraph("<b>วันที่เซ็นสัญญา:</b>", THAI_BOLD), Paragraph(format_thai_date(project.contract_signing_date), THAI_NORMAL),
         Paragraph("<b>วันที่เริ่มต้นสัญญา:</b>", THAI_BOLD), Paragraph(format_thai_date(project.start_date), THAI_NORMAL)],
        [Paragraph("<b>วันที่สิ้นสุดสัญญา:</b>", THAI_BOLD), Paragraph(format_thai_date(project.end_date), THAI_NORMAL),
         Paragraph("<b>วันที่สั่งเข้างานจริง:</b>", THAI_BOLD), Paragraph(format_thai_date(project.work_order_date), THAI_NORMAL)],
        [Paragraph("<b>การได้รับคู่ฉบับ:</b>", THAI_BOLD), Paragraph(project.counterpart_status, THAI_NORMAL),
         Paragraph("<b>การโอนสิทธิ์โครงการ:</b>", THAI_BOLD), Paragraph(f"{project.right_assignment} ({project.right_assignment_percentage or 0}%)", THAI_NORMAL)],
        [Paragraph("<b>วงเงินค้ำประกันสัญญารวม:</b>", THAI_BOLD), Paragraph(format_currency(project.guarantee_amount), THAI_NORMAL),
         Paragraph("<b>รูปแบบหลักประกัน:</b>", THAI_BOLD), Paragraph(project.guarantee_payment_type, THAI_NORMAL)]
    ]
    
    info_table = Table(info_data, colWidths=[120, 150, 120, 165])
    info_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8fafc')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Section 2: Deliverables List
    story.append(Paragraph("<b>2. งวดงานส่งมอบสัญญาหลัก</b>", THAI_BOLD))
    story.append(Spacer(1, 5))
    
    deliv_headers = [
        Paragraph("<b>งวดที่ / รายการส่งมอบพัสดุ</b>", HEADER_STYLE),
        Paragraph("<b>งบประมาณ</b>", HEADER_STYLE),
        Paragraph("<b>เลขเอกสารใบส่งของ</b>", HEADER_STYLE),
        Paragraph("<b>กำหนดวันส่งมอบ</b>", HEADER_STYLE),
        Paragraph("<b>สถานะดำเนินการ</b>", HEADER_STYLE)
     ]
    
    deliv_data = [deliv_headers]
    total_deliv_budget = 0.0
    for d in project.deliverables:
        total_deliv_budget += d.budget or 0.0
        
        name_cell = Paragraph(f"<b>{d.name}</b>" + (f" ({d.milestone})" if d.milestone else ""), THAI_NORMAL)
        budget_cell = Paragraph(format_currency(d.budget), THAI_RIGHT)
        
        # Determine document details based on assignment status
        doc_no = d.delivery_no or "-"
        if project.right_assignment == "โอนสิทธิ์":
            doc_no = f"ภายใน: {d.internal_delivery_no or '-'}<br/>ภายนอก: {d.external_delivery_no or '-'}"
        doc_cell = Paragraph(doc_no, THAI_NORMAL)
        
        status_color = "#3b82f6"
        if d.status == "ส่งมอบแล้ว":
            status_color = "#10b981"
        status_cell = Paragraph(f"<font color='{status_color}'><b>{d.status}</b></font>", THAI_CENTER)
        
        deliv_data.append([
            name_cell,
            budget_cell,
            doc_cell,
            Paragraph(format_thai_date(d.due_date), THAI_CENTER),
            status_cell
        ])
        
    # Append total
    deliv_data.append([
        Paragraph("<b>รวมวงเงินงวดงานส่งมอบทั้งหมด</b>", THAI_CENTER),
        Paragraph(f"<b>{format_currency(total_deliv_budget)}</b>", THAI_RIGHT),
        "", "", ""
    ])
    
    deliv_widths = [200, 85, 110, 80, 80]
    deliv_table = Table(deliv_data, colWidths=deliv_widths)
    deliv_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4f46e5')),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('SPAN', (0, -1), (0, -1)),
        ('SPAN', (1, -1), (1, -1)),
        ('SPAN', (2, -1), (4, -1)),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#4f46e5')),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#4f46e5')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ])
    for r in range(1, len(deliv_data) - 1):
        if r % 2 == 0:
            deliv_style.add('BACKGROUND', (0, r), (-1, r), colors.HexColor('#f8fafc'))
            
    deliv_table.setStyle(deliv_style)
    story.append(deliv_table)
    story.append(Spacer(1, 20))
    
    # Section 3: PO list
    story.append(Paragraph("<b>3. รายการจัดซื้อวัสดุอุปกรณ์ (POs) ภายใต้โครงการ</b>", THAI_BOLD))
    story.append(Spacer(1, 5))
    
    po_headers = [
        Paragraph("<b>เลขที่ PO</b>", HEADER_STYLE),
        Paragraph("<b>รายการวัสดุ</b>", HEADER_STYLE),
        Paragraph("<b>งบประมาณ PO</b>", HEADER_STYLE),
        Paragraph("<b>ผู้จัดซื้อ / คู่ค้า</b>", HEADER_STYLE),
        Paragraph("<b>กำหนดส่งของ</b>", HEADER_STYLE),
        Paragraph("<b>สถานะจัดส่ง</b>", HEADER_STYLE)
    ]
    
    po_data = [po_headers]
    total_po_budget = 0.0
    for po in project.purchase_orders:
        total_po_budget += po.budget or 0.0
        
        po_data.append([
            Paragraph(f"<b>{po.po_number}</b>", THAI_NORMAL),
            Paragraph(po.material_type, THAI_NORMAL),
            Paragraph(format_currency(po.budget), THAI_RIGHT),
            Paragraph(po.contractor, THAI_NORMAL),
            Paragraph(format_thai_date(po.due_date), THAI_CENTER),
            Paragraph(f"<b>{po.delivery_status}</b>", THAI_CENTER)
        ])
        
    po_data.append([
        Paragraph("<b>รวมงบประมาณจัดซื้อ PO ทั้งสิ้น</b>", THAI_CENTER),
        "",
        Paragraph(f"<b>{format_currency(total_po_budget)}</b>", THAI_RIGHT),
        "", "", ""
    ])
    
    po_widths = [90, 110, 85, 120, 80, 70]
    po_table = Table(po_data, colWidths=po_widths)
    po_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0ea5e9')),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#cbd5e1')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('SPAN', (0, -1), (1, -1)),
        ('SPAN', (2, -1), (2, -1)),
        ('SPAN', (3, -1), (5, -1)),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#0ea5e9')),
        ('LINEBELOW', (0, -1), (-1, -1), 2, colors.HexColor('#0ea5e9')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ])
    for r in range(1, len(po_data) - 1):
        if r % 2 == 0:
            po_style.add('BACKGROUND', (0, r), (-1, r), colors.HexColor('#f8fafc'))
            
    po_table.setStyle(po_style)
    story.append(po_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer

def export_po_detail_to_pdf(po):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )
    
    story = []
    
    story.append(Paragraph(f"<b>รายงานใบสั่งซื้อวัสดุ: {po.po_number}</b>", TITLE_STYLE))
    story.append(Paragraph(f"พิมพ์ ณ วันที่: {format_thai_date(date.today())} | ออกโดยระบบบริหารจัดการสัญญาโครงการ", SUBTITLE_STYLE))
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("<b>ข้อมูลรายละเอียดใบสั่งซื้อ PO</b>", THAI_BOLD))
    story.append(Spacer(1, 5))
    
    proj_name = po.project.name if po.project else "-"
    owner_name = po.project.owner if po.project else "-"
    
    metadata = [
        [Paragraph("<b>เลขที่ใบสั่งซื้อ PO:</b>", THAI_BOLD), Paragraph(po.po_number, THAI_NORMAL)],
        [Paragraph("<b>ชื่อโครงการอ้างอิง:</b>", THAI_BOLD), Paragraph(proj_name, THAI_NORMAL)],
        [Paragraph("<b>เจ้าของโครงการ / หน่วยงาน:</b>", THAI_BOLD), Paragraph(owner_name, THAI_NORMAL)],
        [Paragraph("<b>ประเภทวัสดุ / รายการจัดซื้อ:</b>", THAI_BOLD), Paragraph(po.material_type, THAI_NORMAL)],
        [Paragraph("<b>งบประมาณใบสั่งซื้อ PO:</b>", THAI_BOLD), Paragraph(format_currency(po.budget), THAI_NORMAL)],
        [Paragraph("<b>ผู้จัดซื้อ / คู่ค้า:</b>", THAI_BOLD), Paragraph(po.contractor, THAI_NORMAL)],
        [Paragraph("<b>วันที่สั่งซื้อ:</b>", THAI_BOLD), Paragraph(format_thai_date(po.po_date), THAI_NORMAL)],
        [Paragraph("<b>ระยะเวลาจัดส่ง (วัน):</b>", THAI_BOLD), Paragraph(f"{po.delivery_duration_days} วัน", THAI_NORMAL)],
        [Paragraph("<b>กำหนดเวลาส่งมอบสินค้า:</b>", THAI_BOLD), Paragraph(format_thai_date(po.due_date), THAI_NORMAL)],
        [Paragraph("<b>สถานะการจัดส่ง:</b>", THAI_BOLD), Paragraph(po.delivery_status, THAI_NORMAL)],
        [Paragraph("<b>เลขที่ใบส่งของ / ส่งมอบของ:</b>", THAI_BOLD), Paragraph(po.delivery_no or "-", THAI_NORMAL)],
        [Paragraph("<b>วันที่ส่งมอบจริง:</b>", THAI_BOLD), Paragraph(format_thai_date(po.delivery_date), THAI_NORMAL)],
        [Paragraph("<b>ชื่อเอกสารใบสั่งซื้อ PO:</b>", THAI_BOLD), Paragraph(po.po_file_filename or "-", THAI_NORMAL)],
        [Paragraph("<b>ชื่อเอกสารใบเสนอราคา:</b>", THAI_BOLD), Paragraph(po.quotation_file_filename or "-", THAI_NORMAL)],
        [Paragraph("<b>ชื่อเอกสารใบส่งของ:</b>", THAI_BOLD), Paragraph(po.delivery_file_filename or "-", THAI_NORMAL)]
    ]
    
    po_table = Table(metadata, colWidths=[180, 375])
    po_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8fafc')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
    ]))
    
    story.append(po_table)
    
    doc.build(story)
    buffer.seek(0)
    return buffer
