import base64
import time
from pathlib import Path

from openai import OpenAI

from app.core.config import Settings
from app.services.openai_retry import call_with_retry


class VisionService:
    """GPT-4o-mini vision captions for video keyframes."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required for vision captioning.")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.vision_model
        self._settings = settings

    def caption_image(self, image_path: Path) -> str:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")

        def _call() -> str:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Describe this video frame briefly for semantic search indexing. "
                                    "Focus on visible actions and objects."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{encoded}",
                                    "detail": "low",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=150,
            )
            content = response.choices[0].message.content
            if not content:
                raise RuntimeError("Vision model returned an empty caption")
            return content.strip()

        return call_with_retry(
            _call,
            max_retries=self._settings.openai_max_retries,
            min_delay_seconds=self._settings.openai_retry_min_delay_seconds,
            label="vision",
        )

    def caption_images(self, image_paths: list[Path]) -> list[str]:
        """Caption multiple frames with spacing to avoid TPM bursts."""
        captions: list[str] = []
        delay = self._settings.vision_call_delay_seconds
        for index, path in enumerate(image_paths):
            if index > 0 and delay > 0:
                time.sleep(delay)
            captions.append(self.caption_image(path))
        return captions
