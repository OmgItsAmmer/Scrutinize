from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.vision_service import VisionService


@pytest.mark.unit
def test_vision_service_returns_caption(tmp_path):
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"fake-image")

    settings = Settings(openai_api_key="test-key")
    service = VisionService(settings)
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="A person drinking milk"))]

    with patch.object(service._client.chat.completions, "create", return_value=response):
        caption = service.caption_image(image_path)

    assert caption == "A person drinking milk"
