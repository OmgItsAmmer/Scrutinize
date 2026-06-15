#!/usr/bin/env python3
"""Upload a small test file to Cloudinary to verify credentials."""

from app.core.config import get_settings
from app.services.cloudinary_storage import CloudinaryStorage


def main() -> None:
    storage = CloudinaryStorage(get_settings())
    result = storage.upload_bytes(
        b"Scrutinize Cloudinary smoke test",
        filename="smoke.txt",
        modality="text",
        resource_type="raw",
    )
    print("public_id:", result.public_id)
    print("url:", result.secure_url)


if __name__ == "__main__":
    main()
