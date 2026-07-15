import os
import sys
import uuid
import html
import re
import json
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None

mcp = FastMCP("Scrutinize MCP Server") if FastMCP else None


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
    # Since we are running in backend/app/services/v2/mcp_servers/, resolve relative to repo root
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


async def web_search(query: str, limit: int = 3) -> str:
    """
    Search the web for real-time technology/AI news, startup funding, or tech events.
    Returns search results as a JSON string containing list of dicts with title, url, snippet, and content.
    """
    from app.core.config import Settings
    from app.services.web_search import WebSearchService

    settings = Settings()
    if not settings.enable_web_search:
        return json.dumps([])

    service = WebSearchService(settings)
    try:
        results = await service.search(query, limit=limit)
        if not results:
            return json.dumps([])
        urls = [res["url"] for res in results]
        contents = await service.scrape_urls_parallel(urls)

        formatted = []
        for i, res in enumerate(results):
            content = contents[i].strip() if i < len(contents) else ""
            if not content:
                content = res.get("snippet", "")
            if len(content) > 8000:
                content = content[:8000] + "..."
            formatted.append({
                "title": res.get("title", "Web Result"),
                "url": res.get("url", ""),
                "snippet": res.get("snippet", ""),
                "content": content
            })
        return json.dumps(formatted)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("MCP Web search failed: %s", e)
        return json.dumps([])
    finally:
        await service.close()


if mcp:
    generate_pdf = mcp.tool()(generate_pdf)
    web_search = mcp.tool()(web_search)

if __name__ == "__main__":
    if not mcp:
        raise RuntimeError("The 'mcp' package is required to run the MCP server.")
    mcp.run()
