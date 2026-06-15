from pathlib import Path

from app.models.file import FileModality
from app.services.audio_processor import AUDIO_EXTENSIONS
from app.services.text_processor import TEXT_EXTENSIONS
from app.services.video_processor import VIDEO_EXTENSIONS

ALLOWED_TEXT_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/x-markdown",
    "application/octet-stream",
}

ALLOWED_AUDIO_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a",
    "video/mp4",
    "application/octet-stream",
}

ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "application/octet-stream",
}

CONTENT_TYPES_BY_MODALITY = {
    FileModality.TEXT: ALLOWED_TEXT_CONTENT_TYPES,
    FileModality.AUDIO: ALLOWED_AUDIO_CONTENT_TYPES,
    FileModality.VIDEO: ALLOWED_VIDEO_CONTENT_TYPES,
}

ALL_ALLOWED_EXTENSIONS = TEXT_EXTENSIONS | AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


def detect_modality(filename: str) -> FileModality | None:
    extension = Path(filename).suffix.lower()
    if extension in TEXT_EXTENSIONS:
        return FileModality.TEXT
    if extension in AUDIO_EXTENSIONS:
        return FileModality.AUDIO
    if extension in VIDEO_EXTENSIONS:
        return FileModality.VIDEO
    return None


def cloudinary_resource_type(modality: FileModality) -> str:
    if modality == FileModality.TEXT:
        return "raw"
    return "video"


def ingestion_stage(modality: FileModality) -> str:
    return f"{modality.value}_ingestion"


def validate_content_type(modality: FileModality, content_type: str | None) -> bool:
    normalized = (content_type or "").split(";")[0].strip().lower()
    if not normalized:
        return True
    return normalized in CONTENT_TYPES_BY_MODALITY[modality]
