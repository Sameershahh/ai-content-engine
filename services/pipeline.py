"""
services/pipeline.py — End-to-end orchestrator for High-End Reels.
Integrates:
- ScraperService (Discovery)
- AIBrainService (Scripts)
- VoiceGenService (Narration)
- VisualGenService (AI Video Clips)
- VideoEngineService (High-Impact Rendering)
"""
from __future__ import annotations
import asyncio
import traceback
import uuid
from pathlib import Path
from typing import Optional

from core.config import get_settings
from core.models import JobStatus, PipelineRequest, PipelineResult
from core.logging import get_logger
from services.scraper import ScraperService
from services.ai_brain import AIBrainService
from services.voice_gen import VoiceGenService
from services.visual_gen import VisualGenService
from services.video_engine import VideoEngineService
from services.drive_uploader import DriveUploaderService
from utils.file_utils import ensure_dirs

logger = get_logger("pipeline")
settings = get_settings()

_JOBS: dict[str, PipelineResult] = {}

class PipelineOrchestrator:
    def __init__(self) -> None:
        self.scraper = ScraperService()
        self.brain = AIBrainService()
        self.voice_gen = VoiceGenService()
        self.visual_gen = VisualGenService()
        self.video_engine = VideoEngineService()
        self.drive = DriveUploaderService()

    def get_job(self, job_id: str) -> Optional[PipelineResult]:
        return _JOBS.get(job_id)

    async def run(self, request: PipelineRequest) -> str:
        job_id = str(uuid.uuid4())
        _JOBS[job_id] = PipelineResult(job_id=job_id, status=JobStatus.QUEUED)
        asyncio.create_task(self._execute(job_id, request))
        return job_id

    async def _execute(self, job_id: str, request: PipelineRequest) -> None:
        _JOBS[job_id].status = JobStatus.RUNNING
        ensure_dirs(settings.output_dir, settings.temp_dir)

        try:
            # ── 1. Discovery ─────────────────────────────────────────────
            if request.custom_topic:
                topic = request.custom_topic
            else:
                topics = await self.scraper.discover_topics(request.subreddits, request.geo)
                topic = await self.brain.select_best_topic(topics)
            
            _JOBS[job_id].topic = topic

            # ── 2. Brainstorming (Script + Visual Prompt) ───────────────
            content, visual_prompt = await self.brain.generate_content(topic)

            # ── 3. Voice & Visual Generation (Parallel) ──────────────────
            logger.info("pipeline_multimodal_gen_start", job_id=job_id)
            voice_task = asyncio.create_task(
                self.voice_gen.generate_speech(content.reel_script, job_id)
            )
            # Try to generate a VIDEO for background, falls back to image internally
            visual_task = asyncio.create_task(
                self.visual_gen.generate_visual(visual_prompt, job_id, mode="video")
            )
            
            audio_path, visual_path = await asyncio.gather(voice_task, visual_task)

            # ── 4. High-End Rendering ─────────────────────────────────────
            logger.info("pipeline_rendering_high_end", job_id=job_id)
            video_task = asyncio.create_task(
                self.video_engine.render_video(
                    visual_path=visual_path,
                    audio_path=audio_path,
                    script=content.reel_script,
                    topic=topic,
                    job_id=job_id,
                )
            )
            text_task = asyncio.create_task(
                self.video_engine.save_text_assets(
                    job_id=job_id,
                    topic=topic,
                    script=content.reel_script,
                    linkedin=content.linkedin_post,
                    hashtags=content.hashtags,
                )
            )
            
            video_path, text_path = await asyncio.gather(video_task, text_task)
            
            _JOBS[job_id].video_path = str(video_path)
            _JOBS[job_id].text_path = str(text_path)

            # ── 5. Delivery (Google Drive) ────────────────────────────────
            try:
                folder_url = await self.drive.upload_job_assets(job_id, video_path, text_path)
                _JOBS[job_id].drive_folder_url = folder_url
            except Exception as e:
                logger.warning("drive_upload_failed", job_id=job_id, error=str(e))

            _JOBS[job_id].status = JobStatus.DONE
            print(f"\n[OK] High-End Reel Ready: {video_path}\n", flush=True)

        except Exception as exc:
            logger.error("pipeline_failed", job_id=job_id, error=str(exc))
            traceback.print_exc()
            _JOBS[job_id].status = JobStatus.FAILED
            _JOBS[job_id].error = str(exc)
