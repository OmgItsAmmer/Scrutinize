from collections.abc import Iterator
from pathlib import Path

import httpx

CONTENT_TYPES_BY_SUFFIX = {
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
}


def content_type_for_filename(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    return CONTENT_TYPES_BY_SUFFIX.get(suffix, "application/octet-stream")


def stream_remote_url(url: str) -> Iterator[bytes]:
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as response:
        response.raise_for_status()
        yield from response.iter_bytes(65536)


def read_local_file(path: Path) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            yield chunk
