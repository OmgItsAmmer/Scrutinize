from pathlib import Path
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.services.media_utils import (
    FFmpegNotFoundError,
    extract_keyframes,
    probe_duration,
    resolve_media_source,
    run_ffmpeg,
)


@pytest.mark.unit
def test_resolve_media_source_uses_existing_local_file(tmp_path):
    local = tmp_path / "clip.mp3"
    local.write_bytes(b"audio")
    resolved = resolve_media_source(str(local), suffix=".mp3")
    assert resolved == local


@pytest.mark.unit
def test_run_ffmpeg_raises_when_binary_missing():
    settings = Settings(ffmpeg_path="missing-ffmpeg")
    with pytest.raises(FFmpegNotFoundError):
        run_ffmpeg(["-version"], settings=settings)


@pytest.mark.unit
def test_probe_duration_parses_ffprobe_output():
    settings = Settings(ffprobe_path="ffprobe")
    with patch(
        "app.services.media_utils.run_ffprobe",
        return_value="12.5\n",
    ):
        assert probe_duration(Path("video.mp4"), settings=settings) == 12.5


@pytest.mark.unit
def test_extract_keyframes_returns_timestamped_paths(tmp_path):
    settings = Settings(
        ffmpeg_path="ffmpeg",
        video_keyframe_interval_seconds=5.0,
        video_max_keyframes=2,
    )
    frames_dir = tmp_path / "frames"
    frame_one = frames_dir / "frame_0001.jpg"
    frame_two = frames_dir / "frame_0002.jpg"

    def fake_ffmpeg(args, *, settings):
        frames_dir.mkdir(parents=True, exist_ok=True)
        frame_one.write_bytes(b"jpg")
        frame_two.write_bytes(b"jpg")

    with patch("app.services.media_utils.run_ffmpeg", side_effect=fake_ffmpeg):
        items = extract_keyframes(Path("video.mp4"), frames_dir, settings=settings)

    assert len(items) == 2
    assert items[0][1] == 0.0
    assert items[1][1] == 5.0
