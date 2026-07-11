import os
import pytest
import tempfile
from unittest.mock import MagicMock

from app.core.config import Settings
from app.core.deps import get_mcp_manager
from app.services.v2.mcp_manager import McpClientManager

@pytest.mark.unit
@pytest.mark.v2
def test_pdf_generator_tool_directly():
    """Verify that the PDF generator server tool compiles to PDF successfully."""
    from app.services.v2.mcp_servers.pdf_generator import generate_pdf
    
    title = "Test PDF Title"
    content = "This is some test content.\nWith markdown **bold** and *italic* formatting."
    
    filepath = generate_pdf(title, content)
    assert os.path.exists(filepath)
    assert filepath.endswith(".pdf")
    
    # Clean up
    try:
        os.remove(filepath)
    except Exception:
        pass

@pytest.mark.unit
@pytest.mark.v2
def test_mcp_client_manager_list_and_call():
    """Verify that McpClientManager correctly spawns the server and list/calls tools."""
    settings = Settings(mcp_pdf_server_enabled=True)
    manager = McpClientManager(settings)
    
    # 1. Test listing tools
    tools = manager.list_tools()
    assert len(tools) > 0
    assert any(t["function"]["name"] == "generate_pdf" for t in tools)
    
    # 2. Test tool execution via Stdio client subprocess
    title = "Subprocess PDF Test"
    content = "Testing PDF compilation through the MCP stdio connection."
    filepath = manager.call_tool("generate_pdf", {
        "title": title,
        "content": content
    })
    
    filepath = filepath.strip()
    assert os.path.exists(filepath)
    assert filepath.endswith(".pdf")
    
    # Clean up
    try:
        os.remove(filepath)
    except Exception:
        pass

@pytest.mark.unit
@pytest.mark.v2
def test_pdf_generate_api_endpoint(client):
    """Verify that the POST /v2/pdf/generate API endpoint correctly handles requests."""
    mock_manager = MagicMock()
    mock_manager.is_enabled.return_value = True
    
    # Create a temporary PDF file to mock the generated result
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 mock content")
        temp_path = f.name
        
    mock_manager.call_tool.return_value = temp_path
    
    client.app.dependency_overrides[get_mcp_manager] = lambda: mock_manager
    
    response = client.post("/v2/pdf/generate", json={
        "title": "Test API PDF",
        "content": "API test content."
    })
    
    client.app.dependency_overrides.pop(get_mcp_manager, None)
    
    try:
        os.remove(temp_path)
    except Exception:
        pass
        
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert b"%PDF-1.4 mock content" in response.content

@pytest.mark.unit
@pytest.mark.v2
def test_pdf_download_api_endpoint(client):
    """Verify that the GET /v2/pdf/download/{filename} API endpoint serves the generated file."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    output_dir = os.path.join(repo_root, "scratch", "generated_pdfs")
    os.makedirs(output_dir, exist_ok=True)
    
    filename = "test_download_file.pdf"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "wb") as f:
        f.write(b"%PDF-1.4 test download")
        
    try:
        response = client.get(f"/v2/pdf/download/{filename}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert b"%PDF-1.4 test download" in response.content
        
        # Test directory traversal prevention
        response_traversal = client.get("/v2/pdf/download/../../etc/passwd")
        assert response_traversal.status_code in (400, 404)
    finally:
        try:
            os.remove(filepath)
        except Exception:
            pass

