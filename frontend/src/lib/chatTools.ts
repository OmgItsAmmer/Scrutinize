export type ChatToolId = "draft_document" | "flowchart" | "slides";

export interface ChatToolConfig {
  id: ChatToolId;
  label: string;
  requestedTool?: "generate_pdf" | "generate_flowchart";
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
    requestedTool: "generate_flowchart",
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

export function resolvePdfDownloadUrl(href: string): string {
  if (href.startsWith("http://") || href.startsWith("https://")) {
    return href;
  }
  const base = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
  return `${base}${href.startsWith("/") ? href : `/${href}`}`;
}

export function parseMessageWithPdf(content: string): {
  displayText: string;
  pdfDownload: { href: string; filename: string } | null;
} {
  const link = extractPdfLink(content);
  if (!link) {
    return { displayText: content, pdfDownload: null };
  }

  let displayText = content.trim();
  displayText = displayText.replace(
    /^PDF generated successfully:\s*\[[^\]]+\]\([^)]+\)\s*/m,
    "",
  );
  displayText = displayText.replace(
    /\n*\[[^\]]+\]\([^)]+\/v2\/pdf\/download\/[^)]+\)\s*$/m,
    "",
  );
  displayText = displayText.trim();
  if (!displayText) {
    displayText = "Your document is ready.";
  }

  return {
    displayText,
    pdfDownload: {
      href: resolvePdfDownloadUrl(link.href),
      filename: filenameFromPdfUrl(link.href),
    },
  };
}
