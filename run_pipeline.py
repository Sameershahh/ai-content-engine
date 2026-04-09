"""
run_pipeline.py — Direct pipeline runner (no FastAPI needed).
Usage:  python run_pipeline.py
        python run_pipeline.py "Your custom topic here"

Set PYTHONUTF8=1 in your shell or this script handles it automatically.
"""
import asyncio
import sys
import os

# Fix Windows cp1252 unicode crash
os.environ.setdefault("PYTHONUTF8", "1")
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


async def main():
    # Import after env fix
    from core.logging import configure_logging
    from services.pipeline import PipelineOrchestrator
    from core.models import PipelineRequest, JobStatus

    configure_logging()

    custom_topic = sys.argv[1] if len(sys.argv) > 1 else "How AI is transforming content creation in 2025"

    print(f"\n[Pipeline] Starting with topic: {custom_topic}\n")

    orchestrator = PipelineOrchestrator()
    request = PipelineRequest(custom_topic=custom_topic)

    # Run directly (not as background task)
    job_id = "direct_run_" + os.urandom(4).hex()

    from core.models import PipelineResult
    from services.pipeline import _JOBS
    from core.models import JobStatus
    _JOBS[job_id] = PipelineResult(job_id=job_id, status=JobStatus.QUEUED)

    print(f"[Pipeline] Job ID: {job_id}")
    print("[Pipeline] Running stages: Gemini -> SiliconFlow -> MoviePy -> Drive\n")

    await orchestrator._execute(job_id, request)

    result = _JOBS[job_id]
    print("\n" + "=" * 60)
    print(f"Status      : {result.status}")
    print(f"Topic       : {result.topic}")
    print(f"Video Path  : {result.video_path}")
    print(f"Text Path   : {result.text_path}")
    print(f"Drive URL   : {result.drive_folder_url or 'N/A (check Drive config)'}")
    if result.error:
        print(f"Error       : {result.error}")
    print("=" * 60 + "\n")

    if result.status == JobStatus.DONE:
        print("[OK] Pipeline completed successfully!")
        abs_out = os.path.abspath('outputs')
        print(f"     Output folder: {abs_out}")
        import glob
        files = glob.glob(os.path.join(abs_out, f"{job_id}*"))
        for f in files:
            size = os.path.getsize(f)
            print(f"     - {os.path.basename(f)} ({size:,} bytes)")
    else:
        print("[FAILED] Pipeline did not complete. See error above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
