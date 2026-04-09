"""
services/image_gen.py — SiliconFlow FLUX image generation (OpenAI-compatible).
Downloads and saves PNG to temp dir.
"""
from __future__ import annotations
import base64
import uuid
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class ImageGenService:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_base_url,
            timeout=120.0,
        )
        self._temp_dir = Path(settings.temp_dir)
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    async def generate_image(self, prompt: str, job_id: str) -> Path:
        """
        Calls SiliconFlow image generation endpoint.
        Returns path to saved PNG file.
        """
        logger.info("image_gen_start", job_id=job_id, prompt=prompt[:80])

        try:
            response = await self._client.images.generate(
                model=settings.siliconflow_image_model,
                prompt=prompt,
                n=1,
                size="1024x1024",
            )

            image_data = response.data[0]
            output_path = self._temp_dir / f"{job_id}_bg.png"

            if image_data.b64_json:
                # Base64 response
                img_bytes = base64.b64decode(image_data.b64_json)
                output_path.write_bytes(img_bytes)
            elif image_data.url:
                # URL response — download async
                async with httpx.AsyncClient(timeout=60.0) as http:
                    r = await http.get(image_data.url)
                    r.raise_for_status()
                    output_path.write_bytes(r.content)
            else:
                raise ValueError("SiliconFlow returned no image data")

            abs_path = output_path.resolve()
            print(f"[ImageGen] Image saved: {abs_path}", flush=True)
            logger.info("image_gen_done", job_id=job_id, path=str(abs_path))
            return output_path

        except Exception as exc:
            print(f"[ImageGen] SiliconFlow failed ({exc}), using gradient fallback", flush=True)
            logger.warning("image_gen_fallback", job_id=job_id, error=str(exc))
            return await self._generate_fallback_image(job_id)

    async def _generate_fallback_image(self, job_id: str) -> Path:
        """Creates a gradient placeholder if API fails."""
        from PIL import Image, ImageDraw
        import asyncio

        def _make():
            img = Image.new("RGB", (1080, 1920), color=(15, 15, 30))
            draw = ImageDraw.Draw(img)
            for y in range(1920):
                r = int(15 + (y / 1920) * 30)
                g = int(15 + (y / 1920) * 20)
                b = int(30 + (y / 1920) * 60)
                draw.line([(0, y), (1080, y)], fill=(r, g, b))
            path = self._temp_dir / f"{job_id}_bg.png"
            img.save(path)
            return path

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _make)
