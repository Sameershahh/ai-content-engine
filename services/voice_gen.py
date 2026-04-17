"""
services/voice_gen.py — SiliconFlow TTS (primary) with gTTS fallback.
Generates an MP3 voiceover for the reel.
"""
from __future__ import annotations
import asyncio
from pathlib import Path
import httpx
from core.config import get_settings
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class VoiceGenService:
    def __init__(self) -> None:
        self._api_key = settings.siliconflow_api_key
        self._base_url = settings.siliconflow_base_url
        self._temp_dir = Path(settings.temp_dir)
        self._temp_dir.mkdir(parents=True, exist_ok=True)

    async def generate_speech(self, text: str, job_id: str) -> Path:
        """
        Attempts SiliconFlow /audio/speech first.
        Falls back to gTTS (free, keyless) on any failure.
        Returns path to the generated .mp3 file.
        """
        logger.info("voice_gen_start", job_id=job_id)

        # ── Primary: SiliconFlow ─────────────────────────────────────────────
        try:
            result = await self._siliconflow_tts(text, job_id)
            logger.info("voice_gen_done", job_id=job_id, engine="siliconflow")
            return result
        except Exception as exc:
            print(
                f"[VoiceGen] SiliconFlow failed ({exc}), switching to gTTS fallback...",
                flush=True,
            )
            logger.warning("voice_gen_fallback", job_id=job_id, error=str(exc))

        # ── Fallback: gTTS ───────────────────────────────────────────────────
        result = await self._gtts_tts(text, job_id)
        logger.info("voice_gen_done", job_id=job_id, engine="gtts")
        return result

    # ── Internal helpers ─────────────────────────────────────────────────────

    async def _siliconflow_tts(self, text: str, job_id: str) -> Path:
        """Calls the SiliconFlow /audio/speech endpoint."""
        endpoint = f"{self._base_url}/audio/speech"

        # Use full voice identifier required by SiliconFlow
        voice = f"{settings.siliconflow_tts_model}:alex"

        payload = {
            "model": settings.siliconflow_tts_model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(endpoint, json=payload, headers=headers)

            if response.status_code != 200:
                raise RuntimeError(
                    f"SiliconFlow TTS HTTP {response.status_code}: {response.text}"
                )

            output_path = self._temp_dir / f"{job_id}_voice.mp3"
            output_path.write_bytes(response.content)

        abs_path = output_path.resolve()
        print(f"[VoiceGen] SiliconFlow voice saved: {abs_path}", flush=True)
        return output_path

    async def _gtts_tts(self, text: str, job_id: str) -> Path:
        """
        Keyless gTTS fallback — runs in a thread executor to avoid
        blocking the event loop.
        """
        from gtts import gTTS

        def _synthesise() -> Path:
            tts = gTTS(text=text, lang="en", slow=False)
            output_path = self._temp_dir / f"{job_id}_voice.mp3"
            tts.save(str(output_path))
            abs_path = output_path.resolve()
            print(f"[VoiceGen] gTTS voice saved: {abs_path}", flush=True)
            return output_path

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _synthesise)
