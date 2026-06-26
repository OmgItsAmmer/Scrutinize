import { useEffect, useRef, useState } from "react";
import {
  displayV2Answer,
  formatConfidencePercent,
  formatTimestampSeconds,
  V2_LOW_CONFIDENCE_DISCLAIMER,
} from "../lib/format";
import type { SearchSource, SearchV2Response } from "../types/api";

function ModalityBadge({ modality }: { modality: SearchSource["modality"] }) {
  const styles = {
    text: "bg-sky-100 text-sky-800",
    audio: "bg-violet-100 text-violet-800",
    video: "bg-amber-100 text-amber-800",
  }[modality];

  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${styles}`}>
      {modality}
    </span>
  );
}

function TextSourceCard({ source }: { source: SearchSource }) {
  return (
    <article className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-3">
        <div className="flex flex-wrap items-center gap-2 min-w-0">
          <ModalityBadge modality={source.modality} />
          <h3 className="text-sm font-semibold text-zinc-900 break-words">{source.title}</h3>
        </div>
        <span className="text-xs text-zinc-500 shrink-0">{(source.score * 100).toFixed(0)}% match</span>
      </div>
      <p className="text-sm leading-relaxed text-zinc-700">{source.content}</p>
    </article>
  );
}

function AudioSourceCard({ source }: { source: SearchSource }) {
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
    <article className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
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

function VideoSourceCard({ source }: { source: SearchSource }) {
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
    <article className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm">
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

function renderMarkdown(text: string) {
  const lines = text.split("\n");
  let inList = false;
  const listItems: string[] = [];
  const elements: React.ReactNode[] = [];

  const parseInline = (chunk: string): React.ReactNode[] => {
    const parts = chunk.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={index} className="font-semibold text-zinc-950">
            {part.slice(2, -2)}
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
      return part;
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

export function ScrollFade({ children }: { children: React.ReactNode }) {
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

export function SourceCard({ source }: { source: SearchSource }) {
  if (source.modality === "audio") {
    return <AudioSourceCard source={source} />;
  }
  if (source.modality === "video") {
    return <VideoSourceCard source={source} />;
  }
  return <TextSourceCard source={source} />;
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
