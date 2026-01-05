"""Health check and stats API endpoints."""

from typing import Dict

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.database.connection import get_db
from app.database.models import Folder, File, Embedding, IndexingJob
from app.database.schemas import HealthResponse, StatsResponse
from app.core.model_loader import get_model_loader


router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """
    Health check endpoint.

    Returns system status including database connection, model loading, and watcher status.
    """
    # Check database
    db_status = "connected"
    try:
        await db.execute(select(func.count()).select_from(Folder))
    except Exception:
        db_status = "disconnected"

    # Check model
    model_loader = get_model_loader()
    model_loaded = model_loader.is_loaded

    # Check watcher
    from app.main import get_watcher

    watcher = get_watcher()
    watcher_running = watcher.is_running

    # Overall status
    if db_status == "connected" and model_loaded and watcher_running:
        overall = "healthy"
    elif db_status == "connected":
        overall = "degraded"
    else:
        overall = "unhealthy"

    return HealthResponse(
        status=overall,
        database=db_status,
        model_loaded=model_loaded,
        watcher_running=watcher_running,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
) -> StatsResponse:
    """
    System statistics.

    Returns counts of folders, files, embeddings, and active jobs.
    """
    # Count folders
    folder_result = await db.execute(select(func.count()).select_from(Folder))
    total_folders = folder_result.scalar() or 0

    # Count files (non-deleted)
    file_result = await db.execute(
        select(func.count()).select_from(File).where(File.is_deleted == False)
    )
    total_files = file_result.scalar() or 0

    # Count embeddings
    embedding_result = await db.execute(
        select(func.count()).select_from(Embedding)
    )
    total_embeddings = embedding_result.scalar() or 0

    # Count files by modality
    files_by_modality: Dict[str, int] = {}
    for modality in ["audio", "video", "audio_video"]:
        result = await db.execute(
            select(func.count())
            .select_from(File)
            .where(
                (File.modality == modality) & (File.is_deleted == False)
            )
        )
        files_by_modality[modality] = result.scalar() or 0

    # Count deleted files
    deleted_result = await db.execute(
        select(func.count()).select_from(File).where(File.is_deleted == True)
    )
    deleted_files = deleted_result.scalar() or 0

    # Count active indexing jobs
    jobs_result = await db.execute(
        select(func.count())
        .select_from(IndexingJob)
        .where(IndexingJob.status.in_(["pending", "running"]))
    )
    active_jobs = jobs_result.scalar() or 0

    return StatsResponse(
        total_folders=total_folders,
        total_files=total_files,
        total_embeddings=total_embeddings,
        files_by_modality=files_by_modality,
        deleted_files=deleted_files,
        active_indexing_jobs=active_jobs,
    )
