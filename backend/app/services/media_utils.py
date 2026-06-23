import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

import httpx

from app.core.config import Settings


class FFmpegNotFoundError(RuntimeError):
    """Raised when ffmpeg/ffprobe binaries are unavailable."""


def resolve_media_source(source: str, *, suffix: str) -> Path:
    """Return a local filesystem path, downloading remote URLs when needed."""
    parsed = urlparse(source)
    if parsed.scheme == "file":
        local = Path(url2pathname(parsed.path))
        if local.is_file():
            return local

    local = Path(source)
    if local.is_file():
        return local

    return download_to_tempfile(source, suffix=suffix)


def download_to_tempfile(url: str, *, suffix: str) -> Path:
    response = httpx.get(url, timeout=120.0, follow_redirects=True)
    response.raise_for_status()
    temp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp.write(response.content)
    temp.close()
    return Path(temp.name)


def run_ffmpeg(args: list[str], *, settings: Settings) -> None:
    command = [settings.ffmpeg_path, *args]
    try:
        subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise FFmpegNotFoundError(
            f"ffmpeg not found at '{settings.ffmpeg_path}'. Install FFmpeg and ensure it is on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise RuntimeError(f"ffmpeg failed: {stderr or exc}") from exc


def run_ffprobe(args: list[str], *, settings: Settings) -> str:
    command = [settings.ffprobe_path, *args]
    try:
        result = subprocess.run(command, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise FFmpegNotFoundError(
            f"ffprobe not found at '{settings.ffprobe_path}'. Install FFmpeg and ensure it is on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        raise RuntimeError(f"ffprobe failed: {stderr or exc}") from exc
    return result.stdout.decode("utf-8", errors="replace")


def probe_duration(input_path: Path, *, settings: Settings) -> float:
    output = run_ffprobe(
        [
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(input_path),
        ],
        settings=settings,
    )
    return float(output.strip())


def extract_audio(input_path: Path, output_path: Path, *, settings: Settings) -> None:
    run_ffmpeg(
        [
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ],
        settings=settings,
    )


def extract_keyframes(
    input_path: Path,
    output_dir: Path,
    *,
    settings: Settings,
) -> list[tuple[Path, float]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    interval = settings.video_keyframe_interval_seconds
    max_width = settings.video_keyframe_max_width
    output_pattern = str(output_dir / "frame_%04d.jpg")
    run_ffmpeg(
        [
            "-y",
            "-i",
            str(input_path),
            "-vf",
            f"fps=1/{interval},scale={max_width}:-1",
            "-frames:v",
            str(settings.video_max_keyframes),
            "-q:v",
            "5",
            output_pattern,
        ],
        settings=settings,
    )
    frames = sorted(output_dir.glob("frame_*.jpg"))[: settings.video_max_keyframes]
    return [(frame, index * interval) for index, frame in enumerate(frames)]
