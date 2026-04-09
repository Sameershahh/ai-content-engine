"""
core/models.py — Shared request/response schemas.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class TrendingTopic(BaseModel):
    title: str
    source: str
    score: float = 0.0
    url: Optional[str] = None


class GeneratedContent(BaseModel):
    topic: str
    reel_script: str
    linkedin_post: str
    hashtags: list[str] = Field(default_factory=list)


class PipelineResult(BaseModel):
    job_id: str
    status: JobStatus
    topic: Optional[str] = None
    video_path: Optional[str] = None
    text_path: Optional[str] = None
    drive_folder_url: Optional[str] = None
    error: Optional[str] = None


class PipelineRequest(BaseModel):
    custom_topic: Optional[str] = Field(
        None,
        description="Skip scraping and use this topic directly.",
    )
    subreddits: Optional[list[str]] = None
    geo: Optional[str] = None
