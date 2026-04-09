"""
utils/file_utils.py — Directory helpers.
"""
from pathlib import Path
from core.logging import get_logger

logger = get_logger(__name__)


def ensure_dirs(*dirs: str) -> None:
    """Accept either *args strings or a single list."""
    # Handle both ensure_dirs("a","b") and ensure_dirs(["a","b"])
    targets = []
    for d in dirs:
        if isinstance(d, list):
            targets.extend(d)
        else:
            targets.append(d)
    for d in targets:
        Path(d).mkdir(parents=True, exist_ok=True)


async def cleanup_temp_files(job_id: str, temp_dir: str = "temp") -> None:
    import aiofiles.os
    for f in Path(temp_dir).glob(f"{job_id}_*"):
        try:
            await aiofiles.os.remove(f)
        except Exception as e:
            logger.warning("temp_cleanup_failed", file=str(f), error=str(e))
