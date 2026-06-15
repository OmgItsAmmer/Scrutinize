#!/usr/bin/env python3
"""Verify ffmpeg and ffprobe are available for video ingestion (M4)."""

import shutil
import sys

from app.core.config import get_settings


def main() -> None:
    settings = get_settings()
    ffmpeg = shutil.which(settings.ffmpeg_path)
    ffprobe = shutil.which(settings.ffprobe_path)

    if not ffmpeg:
        print(f"ffmpeg not found (looked for '{settings.ffmpeg_path}')", file=sys.stderr)
        sys.exit(1)
    if not ffprobe:
        print(f"ffprobe not found (looked for '{settings.ffprobe_path}')", file=sys.stderr)
        sys.exit(1)

    print("ffmpeg:", ffmpeg)
    print("ffprobe:", ffprobe)
    print("ok")


if __name__ == "__main__":
    main()
