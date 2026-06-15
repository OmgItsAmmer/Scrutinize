from dataclasses import dataclass
from typing import Any

import cloudinary
import cloudinary.uploader

from app.core.config import Settings


@dataclass(frozen=True)
class StorageUploadResult:
    public_id: str
    secure_url: str
    resource_type: str
    bytes: int
    format: str | None = None


class CloudinaryStorage:
    """Server-side Cloudinary upload wrapper for Scrutinize raw files."""

    def __init__(self, settings: Settings) -> None:
        if not settings.cloudinary_configured:
            raise RuntimeError(
                "Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME, "
                "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in .env."
            )
        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=True,
        )
        self._folder = settings.cloudinary_folder.strip("/")

    def _folder_path(self, modality: str) -> str:
        return f"{self._folder}/{modality}" if self._folder else modality

    def upload_bytes(
        self,
        data: bytes,
        *,
        filename: str,
        modality: str,
        resource_type: str = "auto",
    ) -> StorageUploadResult:
        result: dict[str, Any] = cloudinary.uploader.upload(
            data,
            folder=self._folder_path(modality),
            public_id=_public_id_from_filename(filename),
            resource_type=resource_type,
            use_filename=False,
            unique_filename=True,
            overwrite=False,
        )
        return _to_upload_result(result)

    def upload_file(
        self,
        path: str,
        *,
        filename: str,
        modality: str,
        resource_type: str = "auto",
    ) -> StorageUploadResult:
        result: dict[str, Any] = cloudinary.uploader.upload(
            path,
            folder=self._folder_path(modality),
            public_id=_public_id_from_filename(filename),
            resource_type=resource_type,
            use_filename=False,
            unique_filename=True,
            overwrite=False,
        )
        return _to_upload_result(result)

    def delete(self, public_id: str, *, resource_type: str = "image") -> dict[str, Any]:
        return cloudinary.uploader.destroy(public_id, resource_type=resource_type)


def _public_id_from_filename(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in stem)
    return safe.strip("-") or "upload"


def _to_upload_result(result: dict[str, Any]) -> StorageUploadResult:
    return StorageUploadResult(
        public_id=result["public_id"],
        secure_url=result["secure_url"],
        resource_type=result.get("resource_type", "raw"),
        bytes=int(result.get("bytes", 0)),
        format=result.get("format"),
    )
