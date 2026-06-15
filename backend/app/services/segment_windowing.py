from dataclasses import dataclass

from app.services.ingestion import TimedContent


@dataclass(frozen=True)
class TranscriptSegment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class KeyframeCaption:
    timestamp: float
    caption: str


def window_transcript_segments(
    segments: list[TranscriptSegment],
    *,
    min_seconds: float = 15.0,
    max_seconds: float = 30.0,
) -> list[TimedContent]:
    """Merge Whisper segments into ~15-30 second windows."""
    if not segments:
        return []

    if min_seconds <= 0 or max_seconds <= 0:
        raise ValueError("min_seconds and max_seconds must be positive")
    if min_seconds > max_seconds:
        raise ValueError("min_seconds must not exceed max_seconds")

    windows: list[TimedContent] = []
    current_text: list[str] = []
    window_start = segments[0].start
    window_end = segments[0].end

    for segment in segments:
        text = segment.text.strip()
        if not text:
            continue

        proposed_end = max(window_end, segment.end)
        proposed_duration = proposed_end - window_start

        if current_text and proposed_duration > max_seconds:
            windows.append(
                TimedContent(
                    content=" ".join(current_text).strip(),
                    start_time=window_start,
                    end_time=window_end,
                )
            )
            current_text = [text]
            window_start = segment.start
            window_end = segment.end
            continue

        if not current_text:
            window_start = segment.start
        current_text.append(text)
        window_end = max(window_end, segment.end)

        duration = window_end - window_start
        if duration >= min_seconds:
            windows.append(
                TimedContent(
                    content=" ".join(current_text).strip(),
                    start_time=window_start,
                    end_time=window_end,
                )
            )
            current_text = []

    if current_text:
        windows.append(
            TimedContent(
                content=" ".join(current_text).strip(),
                start_time=window_start,
                end_time=window_end,
            )
        )

    return windows


def merge_transcript_with_captions(
    windows: list[TimedContent],
    captions: list[KeyframeCaption],
) -> list[TimedContent]:
    """Attach keyframe captions that fall within each transcript window."""
    if not windows and captions:
        return caption_only_windows(captions)

    merged: list[TimedContent] = []
    for window in windows:
        start = window.start_time or 0.0
        end = window.end_time or start
        caption_texts = [
            caption.caption
            for caption in captions
            if start <= caption.timestamp < end
        ]
        parts = [window.content.strip()] if window.content.strip() else []
        if caption_texts:
            parts.append("Visual: " + " ".join(caption_texts))
        if not parts:
            continue
        merged.append(
            TimedContent(
                content="\n".join(parts),
                start_time=window.start_time,
                end_time=window.end_time,
            )
        )
    return merged


def caption_only_windows(
    captions: list[KeyframeCaption],
    *,
    window_seconds: float = 15.0,
) -> list[TimedContent]:
    """Build time windows from captions when no transcript is available."""
    if not captions:
        return []

    sorted_captions = sorted(captions, key=lambda item: item.timestamp)
    windows: list[TimedContent] = []
    bucket: list[str] = []
    window_start = sorted_captions[0].timestamp
    window_end = window_start + window_seconds

    for caption in sorted_captions:
        if bucket and caption.timestamp >= window_end:
            windows.append(
                TimedContent(
                    content="Visual: " + " ".join(bucket),
                    start_time=window_start,
                    end_time=window_end,
                )
            )
            bucket = [caption.caption]
            window_start = caption.timestamp
            window_end = window_start + window_seconds
            continue
        bucket.append(caption.caption)
        window_end = max(window_end, caption.timestamp + window_seconds)

    if bucket:
        windows.append(
            TimedContent(
                content="Visual: " + " ".join(bucket),
                start_time=window_start,
                end_time=window_end,
            )
        )
    return windows
