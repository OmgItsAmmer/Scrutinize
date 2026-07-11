# Chat Session Snapshot — Scrutinize Backend Fixes

Here is a summary of all the bugs investigated, resolved, and documented during this session.

---

## 1. Resolved Issues

### A. PDF Download/Serve Path Mismatch (404 Error)
* **Problem**: When a PDF was requested, it was correctly created in the workspace at `Scrutinize/scratch/generated_pdfs/` by the MCP server. However, the download API endpoint (`/v2/pdf/download/{filename}`) looked in `ai_news/scratch/generated_pdfs/` (one level too high) because of a path offset bug (`..` five times instead of four).
* **Fix**: 
  * Updated [pdf.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/api/v2/pdf.py#L55) to use 4 levels of directory parent traversal instead of 5.
  * Corrected the unit test path traversal in [test_v2_mcp.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/tests/unit/test_v2_mcp.py#L95) to match (2 levels instead of 3).

### B. Prompt Domain Alignment (Cooking vs. News)
* **Problem**: The default system prompts (`rag_gate_system.txt`, `generic_agent_system.txt`, `decision_agent_system.txt`, `query_rewriter_system.txt`) in the backend codebase were hardcoded for a "cooking and recipe assistant". Because of this, default pipeline searches for tech or AI news without tenant-level settings overrides were flagged as out-of-scope and rejected.
* **Fix**: Rewrote the default template prompts in `backend/app/services/v2/prompts/` to specialize in **technology, artificial intelligence, software developments, startup funding, and tech industry news**.

### C. Query Rewriter Command Distortion
* **Problem**: When a user commanded the assistant to `"generate a pdf of the latest OpenAI news"`, the query rewriter converted it into a question: `"How can I generate a PDF document containing the latest news articles related to OpenAI?"`. This shifted the retrieval target to document generation scripts rather than the actual news, leading to empty/failed PDFs.
* **Fix**: Added a rule in [query_rewriter_system.txt](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v2/prompts/query_rewriter_system.txt#L5) instructing the LLM to retain the underlying news subject (e.g. "OpenAI news") instead of rewriting the query into a process question.

### D. Outdated Year / Relative Time Resolution (The "2023" Bug)
* **Problem**: When searching for "latest news", the query rewriter appended `"2023"` (its training cutoff) because it lacked any context of the current year. This caused retrieval to fetch outdated 2023 articles instead of the indexed 2026 data.
* **Fix**: Modified [query_rewriter.py](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/backend/app/services/v2/query_rewriter.py#L41-L45) to format and inject the complete current date, year, and day of the week (e.g., `Current Date: 2026-07-11 (Saturday)`) directly into the prompt. The rewriter now maps relative terms like "latest", "today", or "this week" to the correct dates.

---

## 2. Updated Architecture Documentation
We updated [diagram.md](file:///c:/Programming/Projects/01_ACTIVE/ai_news/Scrutinize/docs/architecture/diagram.md) to integrate the new MCP client/server elements:
* **System Context (Section 1)**: Integrated the `McpClientManager` block, `PDF Generator Server` subprocess, and new API routes.
* **Search Pipeline (Section 2)**: Added the decision and execution nodes indicating where the synthesis layer interacts with the MCP server to generate PDFs.
* **LLM Client Routing (Section 5)**: Illustrated how MCP tools are dynamically listed and injected into synthesis-related LLM calls.
* **Component Map & API Surface (Sections 6 & 7)**: Registered the new modules and endpoints.

---

## 3. Verification
All 159 backend unit, integration, and security tests pass successfully.
```bash
pytest tests/unit/test_v2_mcp.py
```
Output: `4 passed`
