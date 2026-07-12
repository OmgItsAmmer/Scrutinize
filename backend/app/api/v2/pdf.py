import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.deps import get_mcp_manager
from app.services.v2.mcp_manager import McpClientManager

router = APIRouter()

class PdfRequest(BaseModel):
    title: str
    content: str


def _generated_pdf_path(filename: str) -> str:
    if not filename.endswith(".pdf"):
        filename = f"{filename}.pdf"
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    filepath = os.path.abspath(os.path.join(repo_root, "scratch", "generated_pdfs", filename))
    output_dir = os.path.abspath(os.path.join(repo_root, "scratch", "generated_pdfs"))
    if not filepath.startswith(output_dir):
        raise HTTPException(status_code=400, detail="Invalid path parameter.")
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PDF file not found.")
    return filepath

@router.post("/pdf/generate", tags=["v2"])
def generate_pdf_endpoint(
    body: PdfRequest,
    mcp_manager: McpClientManager = Depends(get_mcp_manager),
) -> FileResponse:
    """Directly compile text/markdown content to a PDF file via the local MCP server."""
    if not mcp_manager.is_enabled():
        raise HTTPException(
            status_code=400,
            detail="MCP PDF generation is disabled in settings."
        )

    try:
        # Call the local MCP tool
        filepath = mcp_manager.call_tool("generate_pdf", {
            "title": body.title,
            "content": body.content
        })
        
        filepath = filepath.strip()
        if not os.path.exists(filepath):
            raise HTTPException(
                status_code=500,
                detail=f"MCP server reported file creation, but path does not exist: {filepath}"
            )
            
        return FileResponse(
            path=filepath,
            media_type="application/pdf",
            filename=os.path.basename(filepath),
            content_disposition_type="inline",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {exc}"
        )

@router.get("/pdf/preview/{filename}", tags=["v2"])
def preview_pdf_endpoint(filename: str):
    """Serve a generated PDF for inline browser preview."""
    filepath = _generated_pdf_path(filename)
    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="inline",
        headers={
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/pdf/download/{filename}", tags=["v2"])
def download_pdf_endpoint(filename: str, download: bool = Query(default=True)):
    """Serve a generated PDF as a download."""
    filepath = _generated_pdf_path(filename)
    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=filename,
        content_disposition_type="attachment" if download else "inline",
    )
