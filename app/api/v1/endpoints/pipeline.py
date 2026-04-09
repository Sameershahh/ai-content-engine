"""
app/api/v1/endpoints/pipeline.py — Pipeline REST endpoints.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from core.models import PipelineRequest, PipelineResult, JobStatus
from services.pipeline import PipelineOrchestrator

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])
orchestrator = PipelineOrchestrator()


@router.post("/run", response_model=dict, status_code=202)
async def run_pipeline(request: PipelineRequest):
    """
    Trigger the full content synthesis pipeline.
    Returns a job_id immediately; poll /status/{job_id} for progress.
    """
    job_id = await orchestrator.run(request)
    return {"job_id": job_id, "status": JobStatus.QUEUED}


@router.get("/status/{job_id}", response_model=PipelineResult)
async def get_status(job_id: str):
    """Poll job status and retrieve results."""
    job = orchestrator.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job


@router.get("/jobs", response_model=list[PipelineResult])
async def list_jobs():
    """List all jobs (current session)."""
    return orchestrator.list_jobs()
