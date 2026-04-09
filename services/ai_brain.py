"""
services/ai_brain.py — Gemini via google-genai SDK.
Model fallback chain: tries each model in order on 429/quota errors.
"""
from __future__ import annotations
import asyncio
import json
import re
import time
from functools import partial
from typing import Optional

from google import genai
from google.genai import types
from google.genai.errors import ClientError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from core.config import get_settings
from core.models import TrendingTopic
from core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-3-flash-preview",
]


class AIBrainService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model

    def _run_sync(self, prompt: str, model: str) -> str:
        response = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.8,
                max_output_tokens=1500,
            ),
        )
        return response.text

    async def _generate(self, prompt: str) -> str:
        """Try each model in fallback chain; skip on 429."""
        loop = asyncio.get_running_loop()
        last_exc = None

        # Build trial list: configured model first, then fallbacks (deduped)
        models_to_try = [self._model] + [m for m in FALLBACK_MODELS if m != self._model]

        for model in models_to_try:
            try:
                logger.info("gemini_attempt", model=model)
                result = await loop.run_in_executor(
                    None, partial(self._run_sync, prompt, model)
                )
                if model != self._model:
                    logger.info("gemini_fallback_success", model=model)
                return result
            except ClientError as e:
                err_str = str(e)
                status = getattr(e, "status_code", None) or getattr(e, "code", None)
                is_quota = status == 429 or "RESOURCE_EXHAUSTED" in err_str or "429" in err_str
                is_not_found = status == 404 or "NOT_FOUND" in err_str or "404" in err_str
                if is_quota:
                    retry_wait = 30  # Default to 30s
                    # Try to parse exact retry from error if possible
                    if "retry in" in err_str:
                        try:
                            match = re.search(r"retry in ([\d\.]+)s", err_str)
                            if match:
                                retry_wait = float(match.group(1)) + 1
                        except:
                            pass
                    
                    logger.warning("gemini_quota_retry", model=model, wait=retry_wait)
                    await asyncio.sleep(retry_wait)
                    
                    # Retry the SAME model once before moving to next fallback
                    try:
                        return await loop.run_in_executor(
                            None, partial(self._run_sync, prompt, model)
                        )
                    except Exception:
                        logger.warning("gemini_retry_failed", model=model)
                        last_exc = e
                        continue  # try next model
                elif is_not_found:
                    logger.warning("gemini_model_not_found", model=model)
                    last_exc = e
                    continue  # model deprecated/removed — try next
                raise  # unexpected error — bubble up
            except Exception as e:
                last_exc = e
                logger.warning("gemini_model_error", model=model, error=str(e))
                continue

        raise RuntimeError(
            f"All Gemini models quota-exhausted or failed. Last error: {last_exc}"
        )

    # ── Topic Selection ──────────────────────────────────────────────────────

    async def select_best_topic(self, topics: list[TrendingTopic]) -> str:
        topic_list = "\n".join(
            f"- [{t.source}] {t.title} (score: {t.score})" for t in topics[:20]
        )
        prompt = (
            "You are a viral content strategist.\n"
            "Given these trending topics, select the SINGLE best topic for creating "
            "a 15-second Instagram Reel + LinkedIn post.\n\n"
            "Criteria: high engagement potential, broad appeal, not politically "
            "divisive, works for AI/tech/business audience.\n\n"
            f"Topics:\n{topic_list}\n\n"
            "Reply with ONLY the chosen topic title. No explanation."
        )
        result = await self._generate(prompt)
        return result.strip().strip('"').strip("'")

    # ── Content Generation ───────────────────────────────────────────────────

    async def generate_content(self, topic: str) -> tuple:
        """
        Returns (GeneratedContent, image_prompt_str).
        topic must be a plain string.
        """
        from core.models import GeneratedContent

        prompt = (
            "You are a viral content creator for short-form video and LinkedIn.\n\n"
            f'Topic: "{topic}"\n\n'
            "Return ONLY a single valid JSON object — no markdown fences, no extra text.\n\n"
            "{\n"
            '  "reel_script": "Punchy 15-second Reel script, max 60 words. Hook + 2-3 insights + CTA. Use \\n for line breaks between caption segments.",\n'
            '  "linkedin_post": "150-200 word LinkedIn post. Professional tone, personal insight, ends with a question.",\n'
            '  "hashtags": ["eight", "relevant", "hashtags", "no", "hash", "symbol", "in", "array"],\n'
            '  "image_prompt": "Vivid cinematic Stable Diffusion prompt for a background image representing this topic. No text in image."\n'
            "}"
        )

        raw = await self._generate(prompt)

        # Strip markdown fences if present
        clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()

        try:
            data = json.loads(clean)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", clean)
            if not match:
                raise ValueError(f"Gemini returned unparseable JSON: {raw[:300]}")
            data = json.loads(match.group())

        content = GeneratedContent(
            topic=topic,
            reel_script=data.get("reel_script", "AI is transforming everything.\nAre you ready?"),
            linkedin_post=data.get("linkedin_post", ""),
            hashtags=data.get("hashtags", []),
        )
        image_prompt = data.get(
            "image_prompt",
            f"Cinematic futuristic abstract visualization representing {topic}, "
            "no text, high quality, 8k, dramatic lighting",
        )
        return content, image_prompt
