import pytest

from app.services.cloudinary_utils import parse_cloudinary_url, thumbnail_url_for


@pytest.mark.unit
@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://res.cloudinary.com/demo/video/upload/v123/scrutinize/video/clip.mp4",
            ("scrutinize/video/clip", "video"),
        ),
        (
            "https://res.cloudinary.com/demo/raw/upload/v999/scrutinize/text/notes.txt",
            ("scrutinize/text/notes", "raw"),
        ),
        (
            "https://example.com/notes.txt",
            None,
        ),
    ],
)
def test_parse_cloudinary_url(url, expected):
    assert parse_cloudinary_url(url) == expected


@pytest.mark.unit
def test_thumbnail_url_for_video():
    url = "https://res.cloudinary.com/demo/video/upload/v123/scrutinize/video/clip.mp4"
    thumbnail = thumbnail_url_for(url, cloud_name="demo", modality="video")
    assert thumbnail == (
        "https://res.cloudinary.com/demo/video/upload/so_0,w_160,h_120,c_fill/scrutinize/video/clip.jpg"
    )


@pytest.mark.unit
def test_thumbnail_url_for_non_video_returns_none():
    url = "https://res.cloudinary.com/demo/raw/upload/v123/scrutinize/text/notes.txt"
    assert thumbnail_url_for(url, cloud_name="demo", modality="text") is None
