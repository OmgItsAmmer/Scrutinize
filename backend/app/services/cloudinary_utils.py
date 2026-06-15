import re
from urllib.parse import urlparse

_VERSION_RE = re.compile(r"^v\d+$")


def parse_cloudinary_url(url: str) -> tuple[str, str] | None:
    """Return (public_id, resource_type) from a Cloudinary secure_url."""
    parsed = urlparse(url)
    if parsed.netloc != "res.cloudinary.com":
        return None

    parts = parsed.path.strip("/").split("/")
    if len(parts) < 4 or parts[2] != "upload":
        return None

    resource_type = parts[1]
    rest = parts[3:]
    while rest and (_VERSION_RE.match(rest[0]) or "," in rest[0] or "=" in rest[0]):
        rest = rest[1:]
    if not rest:
        return None

    public_id_with_ext = "/".join(rest)
    public_id = (
        public_id_with_ext.rsplit(".", 1)[0]
        if "." in public_id_with_ext
        else public_id_with_ext
    )
    return public_id, resource_type


def thumbnail_url_for(
    storage_url: str,
    *,
    cloud_name: str,
    modality: str,
    width: int = 160,
    height: int = 120,
) -> str | None:
    """Build a Cloudinary thumbnail URL for library previews."""
    parsed = parse_cloudinary_url(storage_url)
    if parsed is None:
        return None

    public_id, resource_type = parsed
    if modality == "video" and resource_type == "video":
        return (
            f"https://res.cloudinary.com/{cloud_name}/video/upload/"
            f"so_0,w_{width},h_{height},c_fill/{public_id}.jpg"
        )
    return None
