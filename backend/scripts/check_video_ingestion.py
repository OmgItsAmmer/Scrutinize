#!/usr/bin/env python3
"""Manually run the M4 video ingestion pipeline on a local .mp4/.mov file."""

from app.models.file import FileModality
from app.dev.ingestion_check import ensure_modality, parse_path_arg, run_ingestion


def main() -> None:
    args = parse_path_arg("Run video ingestion (M4) on a local file")
    ensure_modality(args.file, FileModality.VIDEO)
    run_ingestion(args.file, expected=FileModality.VIDEO, skip_upload=args.skip_upload)


if __name__ == "__main__":
    main()
