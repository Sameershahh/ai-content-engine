"""
services/video_engine.py — High-End MoviePy 2.x MP4 renderer.
Supports:
- AI Video Backgrounds (cropped to 9:16)
- AI Voiceover Integration
- Dynamic "Pop-in" Subtitles (Word-by-word/Karaoke style)
- Auto-syncing visuals to audio duration
"""
from __future__ import annotations
import asyncio
import textwrap
import traceback
from functools import partial
from pathlib import Path
import numpy as np

from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

WIDTH, HEIGHT = 1080, 1920
FPS = 24

class VideoEngineService:
    def __init__(self) -> None:
        self._output_dir = Path(settings.output_dir).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def _render_video_sync(
        self,
        visual_path: Path,
        audio_path: Path,
        script: str,
        topic: str,
        job_id: str,
    ) -> Path:
        try:
            from moviepy import VideoFileClip, AudioFileClip, VideoClip, CompositeVideoClip, vfx
            from PIL import Image, ImageFilter, ImageDraw, ImageFont

            output_path = self._output_dir / f"{job_id}_reel.mp4"
            print(f"[VideoEngine] Output path: {output_path}", flush=True)

            # ── 1. Load Audio ────────────────────────────────────────────────
            audio = AudioFileClip(str(audio_path))
            duration = audio.duration
            print(f"[VideoEngine] Audio duration: {duration:.2f}s", flush=True)

            # ── 2. Load Visual ───────────────────────────────────────────────
            if visual_path.suffix.lower() in [".mp4", ".mov", ".avi"]:
                # Video Background
                bg_clip = VideoFileClip(str(visual_path))
                # Resize and Crop to 9:16
                bg_w, bg_h = bg_clip.size
                target_ratio = WIDTH / HEIGHT
                if bg_w / bg_h > target_ratio:
                    # Clip is too wide -> crop sides
                    new_w = int(bg_h * target_ratio)
                    bg_clip = bg_clip.cropped(x_center=bg_w/2, width=new_w)
                else:
                    # Clip is too tall -> crop top/bottom
                    new_h = int(bg_w / target_ratio)
                    bg_clip = bg_clip.cropped(y_center=bg_h/2, height=new_h)
                
                bg_clip = bg_clip.resized((WIDTH, HEIGHT))
                
                # Loop video if it's shorter than audio
                if bg_clip.duration < duration:
                    bg_clip = bg_clip.with_effects([vfx.Loop(duration=duration)])
                else:
                    bg_clip = bg_clip.with_duration(duration)
            else:
                # Image Background (Fallback)
                img = Image.open(visual_path).convert("RGB").resize((WIDTH, HEIGHT), Image.LANCZOS)
                img = img.filter(ImageFilter.GaussianBlur(radius=2))
                bg_arr = np.array(img)
                bg_clip = VideoClip(lambda t: bg_arr, duration=duration)

            # ── 3. Subtitle Generation ───────────────────────────────────────
            # Split script into words for dynamic pop-in
            words = script.replace("\n", " ").split()
            if not words:
                words = ["AI", "Innovation", "2025"]
            
            # Group words into chunks (e.g., 2-3 words at a time)
            chunks = []
            chunk_size = 2
            for i in range(0, len(words), chunk_size):
                chunks.append(" ".join(words[i:i + chunk_size]))
            
            time_per_chunk = duration / len(chunks)
            font_main = self._load_font(80) # Larger impactful font
            font_topic = self._load_font(32)
            
            topic_text = (topic[:40] + "...").upper() if len(topic) > 40 else topic.upper()

            def make_subtitle_frame(t: float) -> np.ndarray:
                # Transparent frame for overlays
                frame = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
                draw = ImageDraw.Draw(frame)
                
                # Draw Topic Bar at top
                self._draw_text_centered(
                    draw, topic_text, font_topic,
                    y=int(HEIGHT * 0.1), width=WIDTH,
                    fill=(255, 255, 0), # Yellow highlight
                )

                # Find current chunk
                idx = min(int(t / time_per_chunk), len(chunks) - 1)
                current_text = chunks[idx].upper()

                # Visual "Pop" effect (simple scale/shadow)
                self._draw_text_centered(
                    draw, current_text, font_main,
                    y=int(HEIGHT * 0.45), width=WIDTH,
                    fill=(255, 255, 255),
                    stroke=True,
                    stroke_width=4
                )
                
                return np.array(frame.convert("RGB"))

            # We create the subtitles as a make_frame function that will be composited
            # However, to maintain MoviePy 2.x stability, we can just burn them 
            # into the bg_clip frames directly or use CompositeVideoClip if we are careful.
            
            def final_make_frame(t: float) -> np.ndarray:
                bg_frame = bg_clip.get_frame(t)
                # Convert bg_frame to PIL
                pil_bg = Image.fromarray(bg_frame).convert("RGBA")
                
                # Darken slightly for better text contrast
                overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 60))
                pil_bg = Image.alpha_composite(pil_bg, overlay)
                
                # Draw text
                draw = ImageDraw.Draw(pil_bg)
                
                # Draw Topic
                self._draw_text_centered(
                    draw, topic_text, font_topic,
                    y=int(HEIGHT * 0.1), width=WIDTH,
                    fill=(255, 255, 0),
                )

                # Draw Chunk
                idx = min(int(t / time_per_chunk), len(chunks) - 1)
                current_text = chunks[idx].upper()
                self._draw_text_centered(
                    draw, current_text, font_main,
                    y=int(HEIGHT * 0.45), width=WIDTH,
                    fill=(255, 255, 255),
                    stroke=True,
                    stroke_width=5
                )

                return np.array(pil_bg.convert("RGB"))

            final_clip = VideoClip(final_make_frame, duration=duration)
            final_clip = final_clip.with_audio(audio)
            final_clip = final_clip.with_fps(FPS)

            print(f"[VideoEngine] Rendering high-end reel ({duration:.2f}s)...", flush=True)
            final_clip.write_videofile(
                str(output_path),
                fps=FPS,
                codec="libx264",
                audio_codec="aac",
                preset="medium",
                threads=4,
                logger=None
            )
            
            final_clip.close()
            audio.close()
            bg_clip.close()

            print(f"[VideoEngine] Success! {output_path}", flush=True)
            return output_path

        except Exception as exc:
            logger.error("video_render_failed", job_id=job_id, error=str(exc))
            print(f"[VideoEngine] FAILED: {exc}", flush=True)
            traceback.print_exc()
            raise

    def _load_font(self, size: int):
        from PIL import ImageFont
        candidates = [
            "C:/Windows/Fonts/impact.ttf", # Impact is great for reels
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
            "Arial.ttf",
        ]
        for c in candidates:
            try: return ImageFont.truetype(c, size)
            except: continue
        return ImageFont.load_default(size=size)

    def _draw_text_centered(self, draw, text, font, y, width, fill, stroke=False, stroke_width=2):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        if stroke:
            for dx, dy in [(-stroke_width, -stroke_width), (stroke_width, -stroke_width), 
                           (-stroke_width, stroke_width), (stroke_width, stroke_width)]:
                draw.text((x+dx, y+dy), text, font=font, fill=(0,0,0))
        draw.text((x, y), text, font=font, fill=fill)

    async def render_video(self, visual_path: Path, audio_path: Path, script: str, topic: str, job_id: str) -> Path:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, partial(self._render_video_sync, visual_path, audio_path, script, topic, job_id)
        )

    async def save_text_assets(self, job_id, topic, script, linkedin, hashtags) -> Path:
        import aiofiles
        path = self._output_dir / f"{job_id}_content.txt"
        content = f"TOPIC: {topic}\n\nSCENE SCRIPT:\n{script}\n\nLINKEDIN:\n{linkedin}\n\nTAGS: {' '.join(hashtags)}"
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(content)
        return path
