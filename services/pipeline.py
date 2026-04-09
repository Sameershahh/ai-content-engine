"""
services/pipeline.py — End-to-end orchestrator.
Fixed: correct method names, correct type passing, correct status enum values,
       Drive upload is non-fatal (video still saved locally on Drive failure).
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
from services.image_gen import ImageGenService
from services.video_engine import VideoEngineService
from services.drive_uploader import DriveUploaderService
from utils.file_utils import ensure_dirs

logger = get_logger("pipeline")
settings = get_settings()

# In-memory job store — swap for Redis in multi-worker prod
_JOBS: dict[str, PipelineResult] = {}


class PipelineOrchestrator:
    def __init__(self) -> None:
        self.scraper = ScraperService()
        self.brain = AIBrainService()
        self.image_gen = ImageGenService()
        self.video_engine = VideoEngineService()
        self.drive = DriveUploaderService()

    def get_job(self, job_id: str) -> Optional[PipelineResult]:
        return _JOBS.get(job_id)

    def list_jobs(self) -> list[PipelineResult]:
        return list(_JOBS.values())

    async def run(self, request: PipelineRequest) -> str:
        job_id = str(uuid.uuid4())
        _JOBS[job_id] = PipelineResult(job_id=job_id, status=JobStatus.QUEUED)
        asyncio.create_task(self._execute(job_id, request))
        return job_id

    async def _execute(self, job_id: str, request: PipelineRequest) -> None:
        _JOBS[job_id].status = JobStatus.RUNNING
        ensure_dirs(settings.output_dir, settings.temp_dir)

        try:
            # ── Step 1: Topic Discovery ──────────────────────────────────
            if request.custom_topic:
                topic = request.custom_topic
                logger.info("pipeline_custom_topic", job_id=job_id, topic=topic)
            else:
                logger.info("pipeline_scraping", job_id=job_id)
                topics = await self.scraper.discover_topics(
                    subreddits=request.subreddits,
                    geo=request.geo,
                )
                if not topics:
                    raise RuntimeError("No topics discovered from scraping")
                topic = await self.brain.select_best_topic(topics)
                logger.info("pipeline_topic_selected", job_id=job_id, topic=topic)

            _JOBS[job_id].topic = topic

            # ── Step 2: AI Content Generation ────────────────────────────
            logger.info("pipeline_content_gen", job_id=job_id)
            # generate_content() takes a plain str — fixed from old broken call
            content, image_prompt = await self.brain.generate_content(topic)
            logger.info("pipeline_content_done", job_id=job_id)

            # ── Step 3: Image Generation ─────────────────────────────────
            logger.info("pipeline_image_gen", job_id=job_id)
            # generate_image() requires (prompt: str, job_id: str) — fixed
            image_path = await self.image_gen.generate_image(image_prompt, job_id)
            logger.info("pipeline_image_done", job_id=job_id, path=str(image_path))

            # ── Step 4: Render Video + Save Text concurrently ────────────
            logger.info("pipeline_rendering", job_id=job_id)
            # render_video() not render_reel() — fixed
            video_task = asyncio.create_task(
                self.video_engine.render_video(
                    image_path=image_path,
                    script=content.reel_script,
                    topic=topic,
                    job_id=job_id,
                )
            )
            text_task = asyncio.create_task(
                self.video_engine.save_text_assets(
                    job_id=job_id,
                    topic=topic,
                    reel_script=content.reel_script,
                    linkedin_post=content.linkedin_post,
                    hashtags=content.hashtags,
                )
            )
            video_path, text_path = await asyncio.gather(video_task, text_task)
            _JOBS[job_id].video_path = str(video_path)
            _JOBS[job_id].text_path = str(text_path)
            logger.info("pipeline_render_done", job_id=job_id, video=str(video_path))

            # ── Step 5: Upload to Google Drive (non-fatal) ────────────────
            logger.info("pipeline_uploading", job_id=job_id)
            try:
                # upload_job_assets() not upload_assets() — fixed
                folder_url = await self.drive.upload_job_assets(
                    job_id=job_id,
                    video_path=video_path,
                    text_path=text_path,
                )
                _JOBS[job_id].drive_folder_url = folder_url
                logger.info("pipeline_upload_done", job_id=job_id, url=folder_url)
            except Exception as drive_err:
                # Drive failure must NOT kill the pipeline — video is already saved locally
                logger.error(
                    "pipeline_drive_skipped",
                    job_id=job_id,
                    reason=str(drive_err),
                )

            _JOBS[job_id].status = JobStatus.DONE
            logger.info("pipeline_complete", job_id=job_id)

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("pipeline_failed", job_id=job_id, error=str(exc))
            logger.error("pipeline_traceback", job_id=job_id, trace=tb)
            _JOBS[job_id].status = JobStatus.FAILED
            _JOBS[job_id].error = str(exc)
