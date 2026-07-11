import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.deps import get_mcp_manager
from app.services.v2.mcp_manager import McpClientManager

router = APIRouter()

class PdfRequest(BaseModel):
    title: str
    content: str

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
            filename=os.path.basename(filepath)
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {exc}"
        )

@router.get("/pdf/download/{filename}", tags=["v2"])
def download_pdf_endpoint(filename: str):
    """Serve a generated PDF file for download."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    filepath = os.path.join(repo_root, "scratch", "generated_pdfs", filename)
    
    # Security check: prevent directory traversal
    filepath = os.path.abspath(filepath)
    output_dir = os.path.abspath(os.path.join(repo_root, "scratch", "generated_pdfs"))
    if not filepath.startswith(output_dir):
        raise HTTPException(status_code=400, detail="Invalid path parameter.")
        
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=404,
            detail="PDF file not found."
        )
        
    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=filename
    )
