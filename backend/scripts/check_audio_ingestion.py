#!/usr/bin/env python3
"""Manually run the M3 audio ingestion pipeline on a local .mp3/.wav/.m4a file."""

from app.models.file import FileModality
from app.dev.ingestion_check import ensure_modality, parse_path_arg, run_ingestion


def main() -> None:
    args = parse_path_arg("Run audio ingestion (M3) on a local file")
    ensure_modality(args.file, FileModality.AUDIO)
    run_ingestion(args.file, expected=FileModality.AUDIO, skip_upload=args.skip_upload)


if __name__ == "__main__":
    main()
