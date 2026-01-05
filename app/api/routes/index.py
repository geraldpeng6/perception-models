"""Indexing API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.schemas import IndexTriggerRequest, IndexStatusListResponse, IndexingJobResponse
from app.services.indexing_service import IndexingService


def get_indexing_service() -> IndexingService:
    """Get indexing service instance."""
    from app.main import get_indexing_service as get_svc

    return get_svc()


router = APIRouter(prefix="/api/v1/index", tags=["indexing"])


@router.post("/trigger", status_code=202)
async def trigger_indexing(
    request: IndexTriggerRequest = IndexTriggerRequest(),
    db: AsyncSession = Depends(get_db),
    indexing_service: IndexingService = Depends(get_indexing_service),
) -> dict:
    """
    Manually trigger indexing for a folder or all folders.

    - **folder_id**: Folder ID (omit for all folders)
    - **mode**: 'full' for complete rescan or 'incremental' for new files only
    """
    try:
        job_id = await indexing_service.index_folder(
            db, folder_id=request.folder_id, mode=request.mode
        )

        return {
            "job_id": job_id,
            "status": "pending",
            "message": "Indexing job started",
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to start indexing: {str(e)}"
        )


@router.get("/status", response_model=IndexStatusListResponse)
async def list_indexing_jobs(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    indexing_service: IndexingService = Depends(get_indexing_service),
) -> IndexStatusListResponse:
    """
    Get status of recent indexing jobs.

    - **limit**: Maximum number of jobs to return
    """
    jobs = await indexing_service.list_recent_jobs(db, limit=limit)

    return IndexStatusListResponse(
        jobs=[
            IndexingJobResponse(
                id=j["id"],
                job_type=j["job_type"],
                folder_id=j["folder_id"],
                status=j["status"],
                total_files=j["total_files"],
                processed_files=j["processed_files"],
                failed_files=j["failed_files"],
                error_message=j["error_message"],
                started_at=j["started_at"],
                completed_at=j["completed_at"],
            )
            for j in jobs
        ]
    )


@router.get("/status/{job_id}", response_model=IndexingJobResponse)
async def get_job_status(
    job_id: int,
    db: AsyncSession = Depends(get_db),
    indexing_service: IndexingService = Depends(get_indexing_service),
) -> IndexingJobResponse:
    """Get detailed status for a specific indexing job."""
    job = await indexing_service.get_job_status(db, job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return IndexingJobResponse(
        id=job["id"],
        job_type=job["job_type"],
        folder_id=job["folder_id"],
        status=job["status"],
        total_files=job["total_files"],
        processed_files=job["processed_files"],
        failed_files=job["failed_files"],
        error_message=job["error_message"],
        started_at=job["started_at"],
        completed_at=job["completed_at"],
    )
