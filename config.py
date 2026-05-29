import os
import io
import re
import discord
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# フォントの登録
font_path = os.path.join("font", "ShipporiMincho-Regular.ttf")
pdfmetrics.registerFont(TTFont("ShipporiMincho", font_path))

# 便箋の制限設定
MAX_CHARS_PER_LINE = 34

def convert_emoji_to_twemoji(text: str) -> str:
    """文章内の絵文字をTwemojiの画像タグに変換する"""
    def replace_emoji(match):
        emoji = match.group(0)
        codepoints = [f"{ord(c):x}" for c in emoji]
        joined_codepoint = "-".join([cp for cp in codepoints if cp != "fe0f"])
        return f'<img src="https://jsdelivr.net{joined_codepoint}.png" width="12" height="12"/>'
    
    emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u200d\u2600-\u27bf\u2b50]')
    return emoji_pattern.sub(replace_emoji, text)

def check_letter_length(content: str) -> int:
    """手紙が何行になるか計算する（上限20行）"""
    lines = content.split('\n')
    total_calculated_lines = 0
    for line in lines:
        if not line:
            total_calculated_lines += 1
            continue
        line_len = len(line)
        actual_lines = (line_len + MAX_CHARS_PER_LINE - 1) // MAX_CHARS_PER_LINE
        total_calculated_lines += max(1, actual_lines)
    return total_calculated_lines

def generate_letter_pdf(target_name: str, sender_name: str, content: str) -> io.BytesIO:
    """手紙のPDFを生成する"""
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=(400, 600))

    # 背景
    c.setFillColorRGB(0.98, 0.96, 0.92)
    c.rect(0, 0, 400, 600, fill=True, stroke=False)

    # 罫線
    c.setStrokeColorRGB(0.76, 0.72, 0.68)
    c.setLineWidth(0.5)
    start_y = 500
    line_spacing = 24
    for i in range(20):
        y = start_y - (i * line_spacing)
        c.line(40, y, 360, y)

    styles = getSampleStyleSheet()
    normal_style = ParagraphStyle(
        name="LetterStyle",
        fontName="ShipporiMincho",
        fontSize=12,
        leading=24,
        textColor=discord.Color.from_rgb(40, 36, 32),
        alignment=TA_LEFT
    )

    # 宛名
    p_target = Paragraph(convert_emoji_to_twemoji(target_name), normal_style)
    p_target.wrap(320, 30)
    p_target.drawOn(c, 40, start_y + 4)

    # 本文
    escaped_content = content.replace('\n', '<br/>')
    html_content = convert_emoji_to_twemoji(escaped_content)
    p_content = Paragraph(html_content, normal_style)
    p_content.wrap(320, 480)
    p_content.drawOn(c, 40, start_y - 480 + 24)

    # 差出人
    if sender_name:
        p_sender = Paragraph(convert_emoji_to_twemoji(sender_name), normal_style)
        p_sender.wrap(320, 30)
        approx_width = len(sender_name) * 12
        x_pos = max(40, 360 - approx_width)
        p_sender.drawOn(c, x_pos, start_y - (20 * line_spacing) - 4)

    c.showPage()
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer
