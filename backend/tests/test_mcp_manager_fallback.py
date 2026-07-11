from app.services.v2.mcp_manager import McpClientManager


class FakeSettings:
    mcp_pdf_server_enabled = True


def test_call_tool_uses_local_pdf_fallback_when_mcp_package_is_missing(monkeypatch):
    manager = McpClientManager(FakeSettings())
    generated = {}

    async def missing_mcp(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'mcp'", name="mcp")

    def fake_generate_pdf(title: str, content: str) -> str:
        generated["title"] = title
        generated["content"] = content
        return "C:/tmp/fallback.pdf"

    monkeypatch.setattr(manager, "_call_tool_async", missing_mcp)
    monkeypatch.setattr(
        "app.services.v2.mcp_servers.pdf_generator.generate_pdf",
        fake_generate_pdf,
    )

    filepath = manager.call_tool(
        "generate_pdf",
        {"title": "OpenAI news", "content": "Compiled news content."},
    )

    assert filepath.endswith("fallback.pdf")
    assert generated == {
        "title": "OpenAI news",
        "content": "Compiled news content.",
    }


def test_list_tools_returns_pdf_schema_when_mcp_listing_fails(monkeypatch):
    manager = McpClientManager(FakeSettings())

    async def no_tools(*args, **kwargs):
        return []

    monkeypatch.setattr(manager, "_list_tools_async", no_tools)

    tools = manager.list_tools()

    assert tools[0]["function"]["name"] == "generate_pdf"
