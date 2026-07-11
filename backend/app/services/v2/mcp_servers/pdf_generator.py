import os
import sys
import uuid
import html
import re
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

mcp = FastMCP("PDF Generator") if FastMCP else None

def markdown_to_pdf_paragraph(text: str) -> str:
    # 1. Escape HTML special characters to prevent xml parsing errors
    escaped = html.escape(text)
    # 2. Convert markdown bold (**text**) to <b>text</b>
    escaped = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', escaped)
    # 3. Convert markdown italic (*text*) to <i>text</i>
    escaped = re.sub(r'\*(.*?)\*', r'<i>\1</i>', escaped)
    return escaped

def generate_pdf(title: str, content: str) -> str:
    """
    Generate a formatted PDF document with a title and content.
    Returns the absolute path to the generated PDF.
    """
    # Create the scratch directory for Scrutinize
    # Since we are running in backend/, let's resolve relative to repo root
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
    output_dir = os.path.join(repo_root, "scratch", "generated_pdfs")
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"document_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(output_dir, filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Custom styling
    title_style = ParagraphStyle(
        'PDFTitleStyle',
        parent=styles['Title'],
        fontSize=22,
        leading=26,
        alignment=TA_CENTER,
        spaceAfter=15
    )
    body_style = ParagraphStyle(
        'PDFBodyStyle',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        spaceAfter=8
    )
    
    title_formatted = markdown_to_pdf_paragraph(title)
    story = [
        Paragraph(title_formatted, title_style),
        Spacer(1, 10)
    ]
    
    paragraphs = content.split("\n")
    for p in paragraphs:
        p_clean = p.strip()
        if p_clean:
            story.append(Paragraph(markdown_to_pdf_paragraph(p_clean), body_style))
            story.append(Spacer(1, 4))
            
    doc.build(story)
    return filepath


if mcp:
    generate_pdf = mcp.tool()(generate_pdf)

if __name__ == "__main__":
    if not mcp:
        raise RuntimeError("The 'mcp' package is required to run the PDF MCP server.")
    mcp.run()
