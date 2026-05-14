"""
backend/services/export_service.py — PDF Generation Engine.

This module handles the transformation of Markdown-formatted chat history into a styled,
printable PDF document using the `reportlab` library. It parses the Markdown into HTML, 
cleans it with BeautifulSoup, and then maps HTML tags to ReportLab Flowable objects 
to maintain formatting (bold, italic, code blocks) in the final PDF.
"""
import re
import html
import markdown2
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, HRFlowable, Preformatted

# ─── Color palette ───────────────────────────────────────────────────────────
ACCENT_COLOR = colors.HexColor("#4b44e0")
BLACK        = colors.black
GREY         = colors.HexColor("#444444")
CODE_BG      = colors.HexColor("#f8f8f8")
CODE_BORDER  = colors.HexColor("#dddddd")


def markdown_to_flowables(markdown_text, styles):
    """
    Convert markdown text into ReportLab flowables.
    """
    flowables = []

    # Markdown → HTML
    html_content = markdown2.markdown(
        markdown_text,
        extras=["fenced-code-blocks", "tables", "strike", "task_list", "code-friendly"]
    )

    # ─── CRITICAL FIX: ReportLab Paragraph only supports <b> and <i> ────────
    html_content = html_content.replace("<strong>", "<b>").replace("</strong>", "</b>")
    html_content = html_content.replace("<em>", "<i>").replace("</em>", "</i>")

    # Use 'html.parser' but we want to iterate over all top-level elements
    soup = BeautifulSoup(html_content, "html.parser")
    
    # If markdown2 produced a single block, it might not have a body, 
    # but BeautifulSoup usually handles it. We iterate over the tags.
    elements = soup.find_all(recursive=False)
    if not elements and html_content.strip():
        # Fallback if it's just a single line or weirdly parsed
        elements = soup.contents

    for element in elements:
        # Skip empty strings / whitespace
        if isinstance(element, str):
            if element.strip():
                flowables.append(Paragraph(element.strip(), styles["Normal"]))
            continue

        if element.name is None:
            continue

        # Headings
        if element.name in ["h1", "h2", "h3"]:
            style_name = "Heading1" if element.name == "h1" else "Heading2"
            if element.name == "h3": style_name = "Heading3"
            
            # Explicitly wrap in <b> just in case the style font-switch fails
            txt = f"<b>{element.get_text()}</b>"
            flowables.append(Paragraph(txt, styles[style_name]))

        # Paragraphs
        elif element.name == "p":
            inner_content = element.decode_contents().replace('\n', ' ').strip()
            if inner_content:
                flowables.append(Paragraph(inner_content, styles["Normal"]))

        # Bullet lists
        elif element.name == "ul":
            for li in element.find_all("li", recursive=False):
                # Ensure bullet dots are present and content is formatted
                content = li.decode_contents().strip()
                flowables.append(
                    Paragraph(f"&bull; {content}", styles["BulletStyle"])
                )

        # Numbered lists
        elif element.name == "ol":
            for idx, li in enumerate(element.find_all("li", recursive=False), 1):
                content = li.decode_contents().strip()
                flowables.append(
                    Paragraph(f"{idx}. {content}", styles["BulletStyle"])
                )

        # Code blocks
        elif element.name == "pre":
            flowables.append(Preformatted(element.get_text(), styles["CodeBlock"]))

        # Horizontal rules
        elif element.name == "hr":
            flowables.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))

        flowables.append(Spacer(1, 4))

    return flowables


def generate_chat_pdf(chat_title: str, messages: list[dict]) -> bytes:
    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"DocuChat — {chat_title}",
        author="DocuChat",
    )

    styles = getSampleStyleSheet()

    # ─── Adjust standard styles ──────────────────────────────────────────────
    
    # Normal Text
    normal_style = styles["Normal"]
    normal_style.fontName = "Helvetica"
    normal_style.fontSize = 11
    normal_style.leading = 15
    normal_style.textColor = BLACK
    normal_style.spaceAfter = 8
    normal_style.allowMarkup = True

    # Heading 1
    h1_style = styles["Heading1"]
    h1_style.fontName = "Helvetica-Bold"
    h1_style.fontSize = 20
    h1_style.leading = 24
    h1_style.textColor = BLACK
    h1_style.spaceBefore = 14
    h1_style.spaceAfter = 10
    h1_style.allowMarkup = True

    # Heading 2
    h2_style = styles["Heading2"]
    h2_style.fontName = "Helvetica-Bold"
    h2_style.fontSize = 16
    h2_style.leading = 20
    h2_style.textColor = BLACK
    h2_style.spaceBefore = 12
    h2_style.spaceAfter = 8
    h2_style.allowMarkup = True

    # Heading 3
    h3_style = styles["Heading3"]
    h3_style.fontName = "Helvetica-Bold"
    h3_style.fontSize = 13
    h3_style.leading = 16
    h3_style.textColor = BLACK
    h3_style.spaceBefore = 10
    h3_style.spaceAfter = 6
    h3_style.allowMarkup = True

    # Bullet point style
    styles.add(
        ParagraphStyle(
            name="BulletStyle",
            parent=normal_style,
            leftIndent=20,
            bulletIndent=10,
            spaceAfter=6,
            allowMarkup=True
        )
    )

    # Code block style
    styles.add(
        ParagraphStyle(
            name="CodeBlock",
            fontName="Courier",
            fontSize=10,
            leading=13,
            backColor=CODE_BG,
            borderPadding=10,
            borderRadius=4,
            borderWidth=0.5,
            borderColor=CODE_BORDER,
            leftIndent=10,
            rightIndent=10,
            spaceBefore=10,
            spaceAfter=10
        )
    )

    # Custom Label styles
    label_user_style = ParagraphStyle(
        "LabelUser",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=ACCENT_COLOR,
        spaceBefore=15,
        spaceAfter=5
    )
    
    label_asst_style = ParagraphStyle(
        "LabelAsst",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=GREY,
        spaceBefore=15,
        spaceAfter=5
    )

    # ─── Build story ─────────────────────────────────────────────────────────
    story = []

    # Branding Header
    story.append(Paragraph("<b>DocuChat Export</b>", h1_style))
    story.append(Paragraph(
        f"Conversation: <b>{html.escape(chat_title)}</b> &nbsp;|&nbsp; "
        f"Exported: {datetime.now(timezone.utc).strftime('%B %d, %Y %H:%M UTC')}",
        styles["Normal"]
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.black, spaceAfter=20))

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        # Sender Label
        label = "You" if role == "user" else "DocuChat AI"
        story.append(Paragraph(label, label_user_style if role == "user" else label_asst_style))

        # Use the robust markdown flowable generator
        story.extend(markdown_to_flowables(content, styles))

        story.append(Spacer(1, 10))

    doc.build(story)
    return buffer.getvalue()
