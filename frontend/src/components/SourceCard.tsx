import { useEffect, useRef } from "react";
import { formatTimestampSeconds } from "../lib/format";
import type { SearchSource } from "../types/api";

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
  answer: string;
  sources: SearchSource[];
  searchQuery: string;
};

export function SearchResults({ answer, sources, searchQuery }: SearchResultsProps) {
  return (
    <div className="mx-auto w-full max-w-3xl space-y-6">
      <section className="rounded-2xl border border-zinc-200 bg-white p-4 shadow-sm sm:p-5">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-zinc-500">Answer</p>
        <p className="text-base leading-relaxed text-zinc-900">{answer}</p>
        <p className="mt-3 text-xs text-zinc-500">Searched for: {searchQuery}</p>
      </section>

      {sources.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold text-zinc-900">Sources</h2>
          {sources.map((source) => (
            <SourceCard key={source.segment_id} source={source} />
          ))}
        </section>
      )}
    </div>
  );
}
