# pdf_generator.py

import os
import io
import re
import qrcode

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Image
from reportlab.platypus import Table, TableStyle, Image as RLImage
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Пути к шрифтам и логотипу
FONT_PATH = os.path.join(os.path.dirname(__file__), "DejaVuSans.ttf")
FONT_BOLD_PATH = os.path.join(os.path.dirname(__file__), "DejaVuSans-Bold.ttf")

pdfmetrics.registerFont(TTFont("DejaVuSans", FONT_PATH))
pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", FONT_BOLD_PATH))

def draw_watermark(canvas, doc):
    logo_path = os.path.join(os.path.dirname(__file__), "static", "logo.png")
    page_width, page_height = A4
    logo_width = page_width 
    logo_height = page_height
    x = (page_width - logo_width) / 2
    y = (page_height - logo_height) / 2
    canvas.saveState()
    try:
        canvas.setFillAlpha(0.07)  # 10% opacity
    except AttributeError:
        pass
    canvas.drawImage(logo_path, x, y, width=logo_width, height=logo_height, mask='auto')
    canvas.restoreState()

def text_to_pdf(text: str, product_type="destiny") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=40, rightMargin=40, topMargin=50, bottomMargin=50
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='Body',
        fontName='DejaVuSans',
        fontSize=12,
        leading=16,
        spaceAfter=6,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name='Header',
        fontName='DejaVuSans-Bold',
        fontSize=14,
        leading=18,
        spaceBefore=14,
        spaceAfter=6,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#7C3AED"),
    ))
    styles.add(ParagraphStyle(
        name='BigTitle',
        fontName='DejaVuSans-Bold',
        fontSize=24,
        textColor=colors.HexColor("#7C3AED"),
        leading=28,
        alignment=TA_LEFT,
        spaceAfter=20,
    ))

    story = []

    if product_type == "solyar":
        big_title = Paragraph("Годовой путь (Соляр) — АстроКотский", styles["BigTitle"])
    elif product_type == "income":
        big_title = Paragraph("Карьерный разбор — АстроКотский", styles["BigTitle"])
    else:
        big_title = Paragraph("Карта предназначения — АстроКотский", styles["BigTitle"])
    if product_type == "compatibility":
        big_title = Paragraph("Совместимость — АстроКотский", styles["BigTitle"])


    cat_avatar_path = os.path.join(os.path.dirname(__file__), "static", "cat_avatar.png")
    cat_avatar = RLImage(cat_avatar_path, width=165, height=165)
    title_table = Table(
    [[big_title, cat_avatar]],
    colWidths=[440, 90],
    hAlign='LEFT'
    )
    title_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(title_table)
    story.append(Spacer(1, 24))

    for block in text.strip().split('\n\n'):
        block = block.strip()
        # Markdown-заголовок
        if re.match(r"^#+\s*", block):
            clean = re.sub(r"^#+\s*", "", block)
            story.append(Paragraph(clean, styles["Header"]))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#7C3AED"), spaceBefore=4, spaceAfter=10))
        # Короткая строка — тоже заголовок
        elif (
            len(block) < 50
            and not any(ch in block for ch in "-*:;")
            and not re.match(r"^[-•]", block)
            and block != ""
        ):
            story.append(Paragraph(block, styles["Header"]))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#7C3AED"), spaceBefore=4, spaceAfter=10))
        else:
            for line in block.split('\n'):
                line = line.strip()
                if not line:
                    continue
                line = line.replace("**", "").replace("_", "")
                story.append(Paragraph(line, styles["Body"]))
                story.append(Spacer(1, 4))
        story.append(Spacer(1, 10))

    # QR-код + ссылка внизу
    qr_img = qrcode.make("https://t.me/CosmoAstrologyBot")
    buf_qr = io.BytesIO()
    qr_img.save(buf_qr, format='PNG')
    buf_qr.seek(0)
    qr_image = Image(buf_qr, width=30*mm, height=30*mm)
    story.append(Spacer(1, 40))
    story.append(qr_image)
    story.append(Spacer(1, 4))
    story.append(Paragraph('<font size=10 color="#7C3AED">https://t.me/CosmoAstrologyBot</font>', styles["Body"]))

    doc.build(
        story,
        onFirstPage=draw_watermark,
        onLaterPages=draw_watermark
    )
    return buf.getvalue()

def upload_pdf_to_storage(user_id: str, pdf_bytes: bytes) -> str:
    from supabase_client import supabase  # импортировать client из клиента Supabase
    import time
    bucket = supabase.storage.from_("destiny-reports")
    fname = f"{user_id}_{int(time.time())}.pdf"
    bucket.upload(fname, pdf_bytes)
    return bucket.get_public_url(fname)
