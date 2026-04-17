"""
services/ai_brain.py — Modular Gemini content generation.
Split into multiple calls to ensure reliability and avoid truncation.
"""
from __future__ import annotations
import asyncio
import json
import re
from functools import partial
from typing import Optional

from google import genai
from google.genai import types
from google.genai.errors import ClientError

from core.config import get_settings
from core.models import TrendingTopic, GeneratedContent
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

FALLBACK_MODELS = ["gemini-2.0-flash", "gemini-3-flash-preview"]

class AIBrainService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    @staticmethod
    def _safe_json(raw: str, key: str, default: str) -> str:
        """Parse JSON from Gemini response with graceful fallbacks."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?\n?(.*?)```", r"\1", raw, flags=re.DOTALL).strip()
        # Try strict parse first
        try:
            return json.loads(cleaned).get(key, default)
        except Exception:
            pass
        # Try extracting the value with regex (handles truncated JSON)
        pattern = rf'"{ re.escape(key) }"\s*:\s*"(.*?)"'
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            return match.group(1).replace("\\n", "\n")
        # Last resort: return everything after the colon
        colon_match = re.search(rf'"{ re.escape(key) }"\s*:\s*', cleaned)
        if colon_match:
            return cleaned[colon_match.end():].strip().strip('"').strip()
        return default

    async def _generate(self, prompt: str, json_mode: bool = False) -> str:
        loop = asyncio.get_running_loop()
        models = [self._model] + [m for m in FALLBACK_MODELS if m != self._model]

        config = types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=2048,  # Increased to prevent truncation
        )
        if json_mode:
            config.response_mime_type = "application/json"

        for model in models:
            try:
                print(f"[AIBrain] Attempting {model}...", flush=True)
                # Capture model in closure explicitly
                _model = model
                response = await loop.run_in_executor(
                    None,
                    lambda: self._client.models.generate_content(
                        model=_model, contents=prompt, config=config
                    ),
                )
                return response.text
            except Exception as e:
                print(f"[AIBrain] {model} FAILED: {e}", flush=True)
                logger.warning("gemini_model_failed", model=model, error=str(e))
                continue
        raise RuntimeError("All Gemini models failed.")

    async def select_best_topic(self, topics: list[TrendingTopic]) -> str:
        topic_list = "\n".join(f"- {t.title}" for t in topics[:15])
        prompt = f"Select the single best viral topic for a 15s AI Reel from this list:\n{topic_list}\nReply with ONLY the title."
        res = await self._generate(prompt)
        return res.strip().strip('"')

    async def generate_content(self, topic: str) -> tuple[GeneratedContent, str]:
        """
        Modular generation: Script -> LinkedIn -> Visual Prompt.
        """
        # 1. Script
        script_prompt = (
            f"Write a 15-second high-energy educational Reel script about '{topic}'.\n"
            "Format: JSON with key 'script'. Use \\n for breaks. Max 50 words."
        )
        script_raw = await self._generate(script_prompt, json_mode=True)
        script = self._safe_json(script_raw, "script", "AI is the future.")

        # 2. LinkedIn & Visual Prompt (Parallel)
        li_prompt = f"Write a professional 100-word LinkedIn post based on this script: {script}\nReturn JSON with key 'post'."
        v_prompt = (
            f"Write a short cinematic AI video prompt for background visuals. "
            f"Topic: {topic}. Return JSON with key 'visual_prompt'. Max 30 words."
        )

        tasks = [
            self._generate(li_prompt, json_mode=True),
            self._generate(v_prompt, json_mode=True),
        ]
        li_raw, v_raw = await asyncio.gather(*tasks)

        linkedin = self._safe_json(li_raw, "post", "")
        visual_prompt = self._safe_json(v_raw, "visual_prompt", f"Cinematic futuristic {topic}")

        content = GeneratedContent(
            topic=topic,
            reel_script=script,
            linkedin_post=linkedin,
            hashtags=["ai", "innovation", "tech"],
        )
        return content, visual_prompt
