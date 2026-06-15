import base64
from pathlib import Path

from openai import OpenAI

from app.core.config import Settings


class VisionService:
    """GPT-4o-mini vision captions for video keyframes."""

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key.strip():
            raise RuntimeError("OPENAI_API_KEY is required for vision captioning.")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.vision_model

    def caption_image(self, image_path: Path) -> str:
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
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
                            "image_url": {"url": f"data:image/jpeg;base64,{encoded}"},
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
