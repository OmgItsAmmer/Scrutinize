import pytest

from app.services.ingestion import TimedContent
from app.services.segment_windowing import (
    KeyframeCaption,
    TranscriptSegment,
    caption_only_windows,
    merge_transcript_with_captions,
    window_transcript_segments,
)


@pytest.mark.unit
def test_window_transcript_segments_merges_into_15_to_30_second_buckets():
    segments = [
        TranscriptSegment(start=0.0, end=5.0, text="Intro"),
        TranscriptSegment(start=5.0, end=12.0, text="Middle"),
        TranscriptSegment(start=12.0, end=20.0, text="End"),
    ]
    windows = window_transcript_segments(segments, min_seconds=15.0, max_seconds=30.0)
    assert len(windows) == 1
    assert windows[0].start_time == 0.0
    assert windows[0].end_time == 20.0
    assert "Intro" in windows[0].content


@pytest.mark.unit
def test_window_transcript_segments_splits_when_exceeding_max_seconds():
    segments = [
        TranscriptSegment(start=0.0, end=20.0, text="Part one"),
        TranscriptSegment(start=20.0, end=45.0, text="Part two"),
    ]
    windows = window_transcript_segments(segments, min_seconds=15.0, max_seconds=30.0)
    assert len(windows) == 2
    assert windows[0].end_time == 20.0
    assert windows[1].start_time == 20.0


@pytest.mark.unit
def test_merge_transcript_with_captions_adds_visual_lines():
    windows = [
        TimedContent(
            content="Someone is speaking",
            start_time=0.0,
            end_time=15.0,
        )
    ]
    captions = [KeyframeCaption(timestamp=5.0, caption="A person holds a glass")]
    merged = merge_transcript_with_captions(windows, captions)
    assert len(merged) == 1
    assert "Someone is speaking" in merged[0].content
    assert "Visual: A person holds a glass" in merged[0].content


@pytest.mark.unit
def test_caption_only_windows_when_no_transcript():
    captions = [
        KeyframeCaption(timestamp=0.0, caption="Opening shot"),
        KeyframeCaption(timestamp=10.0, caption="Close-up"),
    ]
    windows = caption_only_windows(captions, window_seconds=15.0)
    assert len(windows) == 1
    assert "Opening shot" in windows[0].content
