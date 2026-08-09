import { useEffect, useRef, useState } from "react";
import {
  displayV2Answer,
  formatConfidencePercent,
  formatPositionLabel,
  formatTimestampSeconds,
  V2_LOW_CONFIDENCE_DISCLAIMER,
} from "../lib/format";
import type { SearchSource, SearchV2Response } from "../types/api";
import { IconDocument, IconX } from "./icons";
import mermaid from "mermaid";

try {
  mermaid.initialize({
    startOnLoad: false,
    theme: "default",
    securityLevel: "loose",
  });
} catch (e) {
  console.error("Failed to initialize mermaid:", e);
}

const preprocessMermaid = (code: string): string => {
  // 1. Extract all double-quoted strings
  const quotedStrings: string[] = [];
  // Regex to match double-quoted strings, accounting for escaped quotes
  const quoteRegex = /"([^"\\]|\\.)*"/g;
  
  let placeholderCode = code.replace(quoteRegex, (match) => {
    quotedStrings.push(match);
    return `__MERMAID_QUOTE_PLACEHOLDER_${quotedStrings.length - 1}__`;
  });

  // 2. Process double bracket shapes in placeholderCode: id([text]) -> id(["text"])
  placeholderCode = placeholderCode.replace(/(\w+)\(\{\{\s*([^"\}]+?)\s*\}\}\)/g, '$1(({"$2"}))');
  placeholderCode = placeholderCode.replace(/(\w+)\(\[\s*([^"\]]+?)\s*\]\)/g, '$1(["$2"])');
  placeholderCode = placeholderCode.replace(/(\w+)\(\(\s*([^")]+?)\s*\)\)/g, '$1(("$2"))');
  placeholderCode = placeholderCode.replace(/(\w+)\s*\[\(\s*([^")]+?)\s*\)\]/g, '$1[("$2")]');
  placeholderCode = placeholderCode.replace(/(\w+)\s*\[\[\s*([^"\]]+?)\s*\]\]/g, '$1([["$2"]])');

  // 3. Process single bracket shapes (if they contain parentheses/commas/colons/etc. and are not placeholders)
  placeholderCode = placeholderCode.replace(/(\w+)\s*\[\s*([^"\]]+?)\s*\]/g, (match, id, text) => {
    if (text.startsWith('__MERMAID_QUOTE_PLACEHOLDER_')) {
      return match;
    }
    if (text.includes('(') || text.includes(')') || text.includes(',') || text.includes(':') || text.includes('&') || text.includes(';')) {
      return `${id}["${text.trim().replace(/"/g, '\\"')}"]`;
    }
    return match;
  });
  
  placeholderCode = placeholderCode.replace(/(\w+)\s*\(\s*([^"\/)]+?)\s*\)/g, (match, id, text) => {
    if (text.startsWith('__MERMAID_QUOTE_PLACEHOLDER_')) {
      return match;
    }
    const isDirection = ['td', 'lr', 'bt', 'rl', 'tb', 'flowchart', 'graph'].includes(id.toLowerCase()) || 
                        ['td', 'lr', 'bt', 'rl', 'tb'].includes(text.trim().toLowerCase());
    if (isDirection) {
      return match;
    }
    if (text.includes('(') || text.includes(')') || text.includes(',') || text.includes(':') || text.includes('&') || text.includes(';') || text.includes(' ')) {
      return `${id}("${text.trim().replace(/"/g, '\\"')}")`;
    }
    return match;
  });

  placeholderCode = placeholderCode.replace(/(\w+)\s*\{\s*([^"\}]+?)\s*\}/g, (match, id, text) => {
    if (text.startsWith('__MERMAID_QUOTE_PLACEHOLDER_')) {
      return match;
    }
    if (text.includes('(') || text.includes(')') || text.includes(',') || text.includes(':') || text.includes('&') || text.includes(';') || text.includes(' ')) {
      return `${id}{"${text.trim().replace(/"/g, '\\"')}"}`;
    }
    return match;
  });

  // 4. Restore the original double-quoted strings
  const finalCode = placeholderCode.replace(/__MERMAID_QUOTE_PLACEHOLDER_(\d+)__/g, (_, index) => {
    return quotedStrings[parseInt(index, 10)];
  });

  return finalCode;
};

export function MermaidDiagram({ code }: { code: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const renderDiagram = async () => {
      if (!containerRef.current) return;
      try {
        setError(null);
        const cleanedCode = preprocessMermaid(code.trim());
        const id = `mermaid-${Math.random().toString(36).substring(2, 11)}`;
        const { svg: renderedSvg } = await mermaid.render(id, cleanedCode);
        if (active) {
          setSvg(renderedSvg);
        }
      } catch (err) {
        console.error("Mermaid rendering failed:", err);
        if (active) {
          setError("Failed to render diagram.");
        }
      }
    };

    renderDiagram();
    return () => {
      active = false;
    };
  }, [code]);

  if (error) {
    return (
      <div className="my-2 rounded-xl border border-rose-200 bg-rose-50 p-4 font-mono text-xs text-rose-700">
        <p className="font-semibold">{error}</p>
        <pre className="mt-1 overflow-x-auto">{code}</pre>
      </div>
    );
  }

  return (
    <div className="my-3 flex justify-center rounded-2xl border border-zinc-200/50 bg-white/40 p-4 shadow-sm backdrop-blur-md dark:bg-zinc-950/20 dark:border-zinc-800/50 overflow-x-auto w-full">
      <div
        ref={containerRef}
        className="w-full flex justify-center [&>svg]:max-w-full [&>svg]:h-auto"
        dangerouslySetInnerHTML={{
          __html: svg || '<span className="text-xs text-zinc-400">Rendering flowchart...</span>',
        }}
      />
    </div>
  );
}


function ModalityBadge({ modality }: { modality: SearchSource["modality"] }) {
  const styles = {
    text: "bg-sky-100 text-sky-800",
    audio: "bg-violet-100 text-violet-800",
  video: "bg-[var(--app-warning-bg)] text-[var(--app-warning)]",
  }[modality];

  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${styles}`}>
      {modality}
    </span>
  );
}

function TextSourceCard({ source, style }: { source: SearchSource; style?: React.CSSProperties }) {
  const positionLabel = formatPositionLabel(source.page_number, source.section_path);
  return (
    <article className="rounded-2xl border p-4 shadow-sm backdrop-blur-md saturate-125" style={style}>
      <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <ModalityBadge modality={source.modality} />
          <h3 className="text-sm font-semibold text-zinc-900 break-words">{source.title}</h3>
          {positionLabel && (
            <span className="text-xs text-zinc-500 shrink-0">{positionLabel}</span>
          )}
        </div>
        <span className="text-xs text-zinc-500 shrink-0">{(source.score * 100).toFixed(0)}% match</span>
      </div>
      <p className="text-sm leading-relaxed text-zinc-700">{source.content}</p>
    </article>
  );
}

function AudioSourceCard({ source, style }: { source: SearchSource; style?: React.CSSProperties }) {
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio || source.start_time == null) {
      return;
    }
    const seek = () => {
      audio.currentTime = source.start_time ?? 0;
    };
    audio.addEventListener("loadedmetadata", seek);
    return () => audio.removeEventListener("loadedmetadata", seek);
  }, [source.source_path, source.start_time]);

  return (
    <article className="rounded-2xl border p-4 shadow-sm backdrop-blur-md saturate-125" style={style}>
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <ModalityBadge modality={source.modality} />
          <h3 className="text-sm font-semibold text-zinc-900 break-words">{source.title}</h3>
        </div>
        {source.start_time != null && (
          <span className="text-xs text-zinc-500 shrink-0">@ {formatTimestampSeconds(source.start_time)}</span>
        )}
      </div>
      <p className="mb-3 text-sm text-zinc-700">{source.content}</p>
      <audio ref={audioRef} controls className="w-full" src={source.source_path} preload="metadata" />
    </article>
  );
}

function VideoSourceCard({ source, style }: { source: SearchSource; style?: React.CSSProperties }) {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const video = videoRef.current;
    if (!video || source.start_time == null) {
      return;
    }
    const seek = () => {
      video.currentTime = source.start_time ?? 0;
    };
    video.addEventListener("loadedmetadata", seek);
    return () => video.removeEventListener("loadedmetadata", seek);
  }, [source.source_path, source.start_time]);

  return (
    <article className="rounded-2xl border p-4 shadow-sm backdrop-blur-md saturate-125" style={style}>
      <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <ModalityBadge modality={source.modality} />
          <h3 className="text-sm font-semibold text-zinc-900 break-words">{source.title}</h3>
        </div>
        {source.start_time != null && (
          <span className="text-xs text-zinc-500 shrink-0">@ {formatTimestampSeconds(source.start_time)}</span>
        )}
      </div>
      <p className="mb-3 text-sm text-zinc-700">{source.content}</p>
      <video
        ref={videoRef}
        controls
        className="w-full rounded-xl bg-black"
        src={source.source_path}
        preload="metadata"
      />
    </article>
  );
}

const getCardStyle = (index: number) => {
  const badgeColors = [
    "var(--chatly-badge-all)",
    "var(--chatly-badge-text)",
    "var(--chatly-badge-audio)",
    "var(--chatly-badge-video)",
  ];
  const color = badgeColors[index % badgeColors.length];
  return {
    backgroundColor: `color-mix(in srgb, ${color} 18%, rgba(255, 255, 255, 0.28))`,
    borderColor: `color-mix(in srgb, ${color} 40%, transparent)`,
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
  };
};

export function CitationButton({
  index,
  title,
  onClick,
}: {
  index: number;
  title: string;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className="inline-flex items-center justify-center gap-1 mx-0.5 px-2.5 py-0.5 rounded-full text-[11px] font-bold text-zinc-950 bg-white/50 border border-white/75 shadow-sm backdrop-blur-md transition-all duration-200 hover:scale-105 hover:bg-white/80 hover:border-white cursor-pointer active:scale-95 select-none"
    >
      <IconDocument className="h-3 w-3 shrink-0 opacity-100" />
      <span className="leading-none">{index + 1}</span>
    </button>
  );
}

function LinkButton({
  label,
  href,
  onClick,
}: {
  label: string;
  href: string;
  onClick?: (href: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onClick?.(href)}
      className="inline-flex items-center rounded-full border border-white/45 bg-white/60 px-2.5 py-1 text-[11px] font-semibold text-zinc-800 shadow-sm backdrop-blur-md transition hover:-translate-y-[1px] hover:bg-white"
    >
      {label}
    </button>
  );
}

function hrefMatchesSource(href: string, source: SearchSource) {
  return href === source.source_path || href === source.segment_id || href === source.file_id;
}

function parseCitations(
  text: string,
  sources?: SearchSource[],
  onSourceClick?: (source: SearchSource, index: number) => void
): React.ReactNode[] {
  if (!sources || sources.length === 0 || !text) {
    return [text];
  }

  const sortedSources = [...sources]
    .map((s, idx) => ({ source: s, index: idx }))
    .filter(item => item.source.title)
    .sort((a, b) => b.source.title.length - a.source.title.length);

  if (sortedSources.length === 0) {
    return [text];
  }

  const escapeRegExp = (str: string) => str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

  const pattern = sortedSources
    .map(item => `\\(\\s*${escapeRegExp(item.source.title)}\\s*\\)`)
    .join("|");

  const regex = new RegExp(`(${pattern})`, "g");
  const parts = text.split(regex);

  return parts.map((part, index) => {
    const trimmed = part.trim();
    if (trimmed.startsWith("(") && trimmed.endsWith(")")) {
      const titleCandidate = trimmed.slice(1, -1).trim();
      const matched = sortedSources.find(
        item => item.source.title.trim() === titleCandidate
      );
      if (matched) {
        return (
          <CitationButton
            key={`cit-${matched.index}-${index}`}
            index={matched.index}
            title={matched.source.title}
            onClick={() => onSourceClick?.(matched.source, matched.index)}
          />
        );
      }
    }
    return part;
  });
}

export function renderMarkdown(
  text: string,
  sources?: SearchSource[],
  onSourceClick?: (source: SearchSource, index: number) => void,
  onLinkClick?: (href: string) => void
) {
  const lines = text.split("\n");
  let inList = false;
  const listItems: string[] = [];
  const elements: React.ReactNode[] = [];

  let inCodeBlock = false;
  let codeBlockContent: string[] = [];
  let codeBlockLang = "";

  const parseInline = (chunk: string): React.ReactNode[] => {
    const parts = chunk.split(/(\[[^\]]+\]\([^)]+\)|\*\*.*?\*\*|`.*?`)/g);
    return parts.flatMap((part, index) => {
      const linkMatch = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch) {
        const [, label, href] = linkMatch;
        const matched = sources?.find((source) => hrefMatchesSource(href, source));
        if (matched) {
          const sourceIndex = sources?.indexOf(matched) ?? 0;
          return (
            <CitationButton
              key={index}
              index={sourceIndex}
              title={matched.title || label}
              onClick={() => onSourceClick?.(matched, sourceIndex)}
            />
          );
        }
        return <LinkButton key={index} label={label} href={href} onClick={onLinkClick} />;
      }
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={index} className="font-semibold text-zinc-950">
            {parseCitations(part.slice(2, -2), sources, onSourceClick)}
          </strong>
        );
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code
            key={index}
            className="rounded bg-zinc-100 px-1.5 py-0.5 font-mono text-xs text-zinc-900"
          >
            {part.slice(1, -1)}
          </code>
        );
      }
      return parseCitations(part, sources, onSourceClick);
    });
  };

  const flushList = (key: number) => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`list-${key}`} className="my-2 list-disc space-y-1 pl-6 text-zinc-800">
          {listItems.map((item, idx) => (
            <li key={idx}>{parseInline(item)}</li>
          ))}
        </ul>
      );
      listItems.length = 0;
      inList = false;
    }
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        const codeText = codeBlockContent.join("\n");
        if (codeBlockLang === "mermaid") {
          elements.push(<MermaidDiagram key={`mermaid-${idx}`} code={codeText} />);
        } else {
          elements.push(
            <pre key={`code-${idx}`} className="my-2 rounded-xl bg-zinc-950 p-4 font-mono text-xs text-zinc-100 overflow-x-auto">
              <code>{codeText}</code>
            </pre>
          );
        }
        inCodeBlock = false;
        codeBlockContent = [];
        codeBlockLang = "";
      } else {
        if (inList) {
          flushList(idx);
        }
        inCodeBlock = true;
        codeBlockLang = trimmed.slice(3).trim().toLowerCase();
      }
      return;
    }

    if (inCodeBlock) {
      codeBlockContent.push(line);
      return;
    }

    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      inList = true;
      listItems.push(trimmed.slice(2));
    } else {
      if (inList) {
        flushList(idx);
      }
      if (trimmed === "") {
        elements.push(<div key={`space-${idx}`} className="h-2" />);
      } else {
        elements.push(
          <p key={`p-${idx}`} className="my-1 text-zinc-800">
            {parseInline(line)}
          </p>
        );
      }
    }
  });

  if (inList) {
    flushList(lines.length);
  }

  return elements;
}

type SourcePreviewModalProps = {
  source: SearchSource;
  index: number;
  onClose: () => void;
};

export function SourcePreviewModal({ source, index, onClose }: SourcePreviewModalProps) {
  const positionLabel = formatPositionLabel(source.page_number, source.section_path);
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center bg-zinc-900/60 p-4 backdrop-blur-md animate-fade-in"
      role="dialog"
      aria-modal="true"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-xl overflow-hidden rounded-3xl border border-white/20 bg-white/80 dark:bg-zinc-900/80 p-6 shadow-2xl backdrop-blur-xl animate-scale-up"
      >
        <div className="mb-4 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="rounded-full bg-white/30 border border-white/40 px-2.5 py-0.5 text-[10px] font-semibold text-zinc-500 uppercase tracking-wider backdrop-blur-sm">
                Source [{index + 1}]
              </span>
              <ModalityBadge modality={source.modality} />
              <span className="text-xs text-zinc-500 font-medium">
                {(source.score * 100).toFixed(0)}% match
              </span>
              {positionLabel && (
                <span className="text-xs text-zinc-500 font-medium">{positionLabel}</span>
              )}
            </div>
            <h3 className="text-lg font-bold text-zinc-900 dark:text-white break-words">
              {source.title}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="rounded-full p-2 text-zinc-500 hover:bg-black/5 dark:hover:bg-white/5 hover:text-zinc-800 dark:hover:text-white transition-all cursor-pointer"
            aria-label="Close"
          >
            <IconX className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-2 space-y-4 max-h-[60vh] overflow-y-auto pr-1 no-scrollbar">
          <div className="rounded-2xl bg-black/5 dark:bg-white/5 border border-white/10 p-4">
            <p className="text-sm leading-relaxed text-zinc-800 dark:text-zinc-200 whitespace-pre-wrap">
              {source.content}
            </p>
            {source.source_path.startsWith("http") && (
              <a
                href={source.source_path}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-flex max-w-full rounded-full border border-white/40 bg-white/40 px-3 py-1 text-xs font-medium text-zinc-700 shadow-sm backdrop-blur-md transition hover:bg-white/70"
              >
                <span className="truncate">{source.source_path}</span>
              </a>
            )}
          </div>

          {source.modality === "audio" && source.source_path && (
            <div className="rounded-2xl bg-black/5 dark:bg-white/5 p-3">
              <audio controls src={source.source_path} className="w-full" autoPlay={false} />
            </div>
          )}

          {source.modality === "video" && source.source_path && (
            <div className="rounded-2xl overflow-hidden bg-black aspect-video border border-white/10">
              <video controls src={source.source_path} className="w-full h-full" autoPlay={false} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ScrollFade({ children, delay = 0 }: { children: React.ReactNode; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        setIsVisible(entry.isIntersecting);
      },
      {
        threshold: 0.05,
        rootMargin: "-10px 0px -10px 0px",
      }
    );

    if (ref.current) {
      observer.observe(ref.current);
    }

    return () => {
      if (ref.current) {
        observer.unobserve(ref.current);
      }
    };
  }, []);

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`transform transition-all duration-700 ease-out ${
        isVisible
          ? "scale-100 translate-y-0 opacity-100"
          : "pointer-events-none scale-98 translate-y-6 opacity-0"
      }`}
    >
      {children}
    </div>
  );
}

export function SourceCard({ source, index = 0 }: { source: SearchSource; index?: number }) {
  const style = getCardStyle(index);

  if (source.modality === "audio") {
    return <AudioSourceCard source={source} style={style} />;
  }
  if (source.modality === "video") {
    return <VideoSourceCard source={source} style={style} />;
  }
  return <TextSourceCard source={source} style={style} />;
}

type SearchResultsProps = {
  result: SearchV2Response;
};

function RouteChip({ route }: { route: SearchResultsProps["result"]["route"] }) {
  const label = route === "rag" ? "Library search" : "Generic";
  const styles =
    route === "rag"
      ? "bg-emerald-100 text-emerald-800"
      : "bg-zinc-100 text-zinc-700";

  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles}`}>
      {label}
    </span>
  );
}

function ConfidenceBadge({ confidence }: { confidence: number | null }) {
  const label = formatConfidencePercent(confidence);
  if (!label) {
    return null;
  }

  return (
    <span className="rounded-full bg-indigo-100 px-2.5 py-0.5 text-xs font-medium text-indigo-800">
      {label}
    </span>
  );
}

export function SearchResults({ result }: SearchResultsProps) {
  const answerText = displayV2Answer(result.answer, result.disclaimer_appended);

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <ScrollFade>
        <section className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm sm:p-5">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <p className="text-xs font-medium uppercase tracking-wide text-zinc-500">Answer</p>
            <RouteChip route={result.route} />
            <ConfidenceBadge confidence={result.confidence} />
            {result.attempts > 1 && (
              <span className="text-xs text-zinc-500">{result.attempts} attempts</span>
            )}
          </div>
          <div className="text-base leading-relaxed text-zinc-900 space-y-2">
            {renderMarkdown(answerText)}
          </div>
          {result.disclaimer_appended && (
            <p className="mt-3 text-xs italic text-amber-700/90">{V2_LOW_CONFIDENCE_DISCLAIMER}</p>
          )}
          <p className="mt-3 text-xs text-zinc-500">Searched for: {result.rewritten_query}</p>
        </section>
      </ScrollFade>

      {result.sources.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-zinc-900">Sources</h2>
          {result.sources.map((source) => (
            <ScrollFade key={source.segment_id}>
              <SourceCard source={source} />
            </ScrollFade>
          ))}
        </section>
      )}
    </div>
  );
}
