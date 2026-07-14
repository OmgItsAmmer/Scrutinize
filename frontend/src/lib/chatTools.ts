export type ChatToolId = "draft_document" | "flowchart" | "slides";

export interface ChatToolConfig {
  id: ChatToolId;
  label: string;
  requestedTool?: "generate_pdf";
}

export const CHAT_TOOLS: ChatToolConfig[] = [
  {
    id: "draft_document",
    label: "Draft Documents",
    requestedTool: "generate_pdf",
  },
  {
    id: "flowchart",
    label: "Build Flowcharts",
    requestedTool: "generate_pdf",
  },
  {
    id: "slides",
    label: "Build Slides",
    requestedTool: "generate_pdf",
  },
];

export function filenameFromPdfUrl(url: string) {
  let name = url.split("?")[0]?.split("/").filter(Boolean).pop() ?? "generated-document.pdf";
  if (!name.endsWith(".pdf")) {
    name = `${name}.pdf`;
  }
  return name;
}

export function pdfPreviewUrl(url: string) {
  let preview = url.replace("/v2/pdf/download/", "/v2/pdf/preview/").split("?")[0] ?? url;
  if (preview.endsWith(".pdf")) {
    preview = preview.slice(0, -4);
  }
  return preview;
}

export function extractPdfLink(content: string): { label: string; href: string } | null {
  const match = content.match(/\[([^\]]+)\]\(([^)]+\/v2\/pdf\/download\/[^)]+)\)/);
  if (!match) return null;
  return { label: match[1], href: match[2] };
}
