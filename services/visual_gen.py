"""
services/visual_gen.py — SiliconFlow Text-to-Video and Image generation.
Generates an MP4 background clip or PNG fallback for the reel.
"""
from __future__ import annotations
import asyncio
import base64
import uuid
from pathlib import Path
import httpx
from openai import AsyncOpenAI

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

class VisualGenService:
    def __init__(self) -> None:
        self._api_key = settings.siliconflow_api_key
        self._base_url = settings.siliconflow_base_url
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self._base_url,
            timeout=120.0,
        )
        self._temp_dir = Path(settings.temp_dir)
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    async def generate_visual(self, prompt: str, job_id: str, mode: str = "video") -> Path:
        """
        Main entry point for visuals. Tries video first, falls back to image.
        """
        if mode == "video":
            try:
                return await self.generate_video_clip(prompt, job_id)
            except Exception as exc:
                logger.warning("video_gen_failed_falling_back", job_id=job_id, error=str(exc))
                print(f"[VisualGen] Video failed, falling back to image...", flush=True)
        
        return await self.generate_image(prompt, job_id)

    async def generate_video_clip(self, prompt: str, job_id: str) -> Path:
        """
        Calls SiliconFlow video generation endpoint.
        Returns path to the generated .mp4 file.
        """
        logger.info("video_gen_start", job_id=job_id, prompt=prompt[:80])
        endpoint = f"{self._base_url}/video/generations"
        
        payload = {
            "model": settings.siliconflow_video_model,
            "prompt": prompt,
        }
        
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json"
        }

        try:
            # Video generation is resource intensive; using a longer timeout
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                
                if response.status_code != 200:
                    raise RuntimeError(f"SiliconFlow Video failed ({response.status_code}): {response.text}")

                data = response.json()
                video_url = None
                
                # SiliconFlow video responses can vary; checking common locations
                if "images" in data and data["images"]:
                     video_url = data["images"][0].get("url")
                elif "data" in data and data["data"]:
                     video_url = data["data"][0].get("url")
                else:
                     video_url = data.get("url")

                if not video_url:
                    raise ValueError(f"SiliconFlow returned no video URL: {data}")

                output_path = self._temp_dir / f"{job_id}_bg.mp4"
                
                # Download the video file
                async with httpx.AsyncClient(timeout=120.0) as downloader:
                    r = await downloader.get(video_url)
                    r.raise_for_status()
                    output_path.write_bytes(r.content)
                
                abs_path = output_path.resolve()
                print(f"[VisualGen] Video saved: {abs_path}", flush=True)
                logger.info("video_gen_done", job_id=job_id, path=str(abs_path))
                return output_path

        except Exception as exc:
            logger.error("video_gen_error", job_id=job_id, error=str(exc))
            raise

    async def generate_image(self, prompt: str, job_id: str) -> Path:
        """
        Original image generation logic as a fallback.
        """
        logger.info("image_gen_start", job_id=job_id)
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
                output_path.write_bytes(base64.b64decode(image_data.b64_json))
            elif image_data.url:
                async with httpx.AsyncClient(timeout=60.0) as http:
                    r = await http.get(image_data.url)
                    r.raise_for_status()
                    output_path.write_bytes(r.content)
            
            abs_path = output_path.resolve()
            print(f"[VisualGen] Image saved (fallback): {abs_path}", flush=True)
            return output_path
        except Exception as exc:
            return await self._generate_fallback_gradient(job_id)

    async def _generate_fallback_gradient(self, job_id: str) -> Path:
        from PIL import Image, ImageDraw
        def _make():
            img = Image.new("RGB", (1080, 1920), color=(20, 20, 40))
            draw = ImageDraw.Draw(img)
            for y in range(1920):
                r = int(20 + (y / 1920) * 40)
                g = int(20 + (y / 1920) * 30)
                b = int(40 + (y / 1920) * 80)
                draw.line([(0, y), (1080, y)], fill=(r, g, b))
            path = self._temp_dir / f"{job_id}_bg.png"
            img.save(path)
            return path
        return await asyncio.get_running_loop().run_in_executor(None, _make)
