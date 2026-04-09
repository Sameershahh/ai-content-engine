"""
services/video_engine.py — MoviePy 2.x MP4 renderer (thread-pool, non-blocking).
Uses VideoClip(make_frame) pattern — correct for MoviePy 2.x.
Produces 1080x1920 (9:16 Reel) with timed captions burned over background image.
No ImageMagick dependency — pure Pillow text rendering.
"""
from __future__ import annotations
import asyncio
import textwrap
import traceback
from functools import partial
from pathlib import Path

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

WIDTH, HEIGHT = 1080, 1920
FPS = 24
DURATION = 15


class VideoEngineService:
    def __init__(self) -> None:
        self._output_dir = Path(settings.output_dir).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)

    # ── Core sync renderer (runs in thread pool) ─────────────────────────────

    def _render_video_sync(
        self,
        image_path: Path,
        script: str,
        topic: str,
        job_id: str,
    ) -> Path:
        try:
            from moviepy import VideoClip
            from PIL import Image, ImageFilter, ImageDraw, ImageFont
            import numpy as np

            output_path = self._output_dir / f"{job_id}_reel.mp4"
            print(f"[VideoEngine] Output path: {output_path}", flush=True)

            # ── Background image ─────────────────────────────────────────────
            bg = Image.open(image_path).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
            bg = bg.filter(ImageFilter.GaussianBlur(radius=4))

            # ── Dark overlay ─────────────────────────────────────────────────
            overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 140))
            bg_rgba = bg.convert("RGBA")
            bg_rgba = Image.alpha_composite(bg_rgba, overlay)
            bg_rgb = bg_rgba.convert("RGB")
            bg_arr = np.array(bg_rgb)  # pre-computed base frame

            # ── Caption lines ─────────────────────────────────────────────────
            lines = [l.strip() for l in script.split("\n") if l.strip()]
            if not lines:
                lines = textwrap.wrap(script, width=32)
            if not lines:
                lines = ["AI is transforming everything.", "Are you ready?"]

            time_per_line = DURATION / len(lines)
            font_large = self._load_font(62)
            font_small = self._load_font(28)

            topic_text = (topic[:48] + "...").upper() if len(topic) > 48 else topic.upper()

            # Pre-render all caption frames as numpy arrays (avoids per-frame PIL overhead)
            rendered_frames: list[np.ndarray] = []
            for line_text in lines:
                frame_img = Image.fromarray(bg_arr.copy())
                draw = ImageDraw.Draw(frame_img)

                # Topic watermark
                self._draw_text_centered(
                    draw, topic_text, font_small,
                    y=int(HEIGHT * 0.08), width=WIDTH,
                    fill=(255, 255, 255),
                )

                # Caption line(s)
                wrapped = textwrap.wrap(line_text, width=28)
                y_start = int(HEIGHT * 0.62)
                for wline in wrapped:
                    self._draw_text_centered(
                        draw, wline, font_large,
                        y=y_start, width=WIDTH,
                        fill=(255, 255, 255),
                        stroke=True,
                    )
                    y_start += 76

                rendered_frames.append(np.array(frame_img))

            print(f"[VideoEngine] Rendered {len(rendered_frames)} caption frames", flush=True)

            # ── MoviePy make_frame function ───────────────────────────────────
            def make_frame(t: float) -> np.ndarray:
                """Returns the correct caption frame for time t."""
                idx = min(int(t / time_per_line), len(rendered_frames) - 1)
                return rendered_frames[idx]

            # ── Build and write video ─────────────────────────────────────────
            clip = VideoClip(make_frame, duration=DURATION)
            clip = clip.with_fps(FPS)

            print(f"[VideoEngine] Writing MP4...", flush=True)
            clip.write_videofile(
                str(output_path),
                fps=FPS,
                codec="libx264",
                audio=False,
                preset="ultrafast",
                threads=2,
                logger=None,
            )
            clip.close()

            if not output_path.exists():
                raise RuntimeError(f"write_videofile completed but file not found: {output_path}")

            file_size = output_path.stat().st_size
            print(f"[VideoEngine] Done! File: {output_path} ({file_size:,} bytes)", flush=True)
            logger.info("video_rendered", job_id=job_id, path=str(output_path), size_bytes=file_size)
            return output_path

        except Exception as exc:
            tb = traceback.format_exc()
            print(f"[VideoEngine] RENDER FAILED:\n{tb}", flush=True)
            logger.error("video_render_failed", job_id=job_id, error=str(exc), trace=tb)
            raise  # re-raise so pipeline catches it properly

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _load_font(self, size: int):
        from PIL import ImageFont
        candidates = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/calibri.ttf",
            "arial.ttf",
            "Arial.ttf",
            "DejaVuSans-Bold.ttf",
            "DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
        for c in candidates:
            try:
                return ImageFont.truetype(c, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default(size=size)

    def _draw_text_centered(
        self,
        draw,
        text: str,
        font,
        y: int,
        width: int,
        fill=(255, 255, 255),
        stroke: bool = False,
    ) -> None:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        if stroke:
            for dx, dy in [(-2, -2), (2, -2), (-2, 2), (2, 2)]:
                draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
        draw.text((x, y), text, font=font, fill=fill)

    # ── Async public API ─────────────────────────────────────────────────────

    async def render_video(
        self,
        image_path: Path,
        script: str,
        topic: str,
        job_id: str,
    ) -> Path:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._render_video_sync, image_path, script, topic, job_id),
        )

    async def save_text_assets(
        self,
        job_id: str,
        topic: str,
        reel_script: str,
        linkedin_post: str,
        hashtags: list[str],
    ) -> Path:
        import aiofiles

        path = self._output_dir / f"{job_id}_content.txt"
        tags = " ".join(f"#{h}" for h in hashtags)

        content = (
            f"TOPIC: {topic}\n"
            f"{'=' * 60}\n\n"
            f"REEL SCRIPT (15s)\n"
            f"{'-' * 40}\n"
            f"{reel_script}\n\n"
            f"LINKEDIN POST\n"
            f"{'-' * 40}\n"
            f"{linkedin_post}\n\n"
            f"HASHTAGS\n"
            f"{'-' * 40}\n"
            f"{tags}\n"
        )
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(content)

        abs_path = path.resolve()
        print(f"[VideoEngine] Text saved: {abs_path}", flush=True)
        logger.info("text_assets_saved", job_id=job_id, path=str(abs_path))
        return path
