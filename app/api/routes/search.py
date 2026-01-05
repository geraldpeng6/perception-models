"""Search API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.schemas import (
    SearchRequest,
    SearchResponse,
)
from app.services.search_service import SearchService


def get_search_service() -> SearchService:
    """Get search service instance."""
    from app.main import get_search_service as get_svc

    return get_svc()


router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """
    Search across indexed files using text, audio, or video query.

    - **query**: Text query or file path for audio/video
    - **query_type**: Type of query ('text', 'audio', 'video')
    - **modalities**: Filter by modalities (default: all)
    - **folder_ids**: Filter by folder IDs
    - **top_k**: Number of results (1-100)
    - **threshold**: Minimum similarity score
    """
    try:
        return await search_service.search(db, request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/file", response_model=SearchResponse)
async def search_by_file(
    query_type: str,  # 'audio' or 'video'
    file: UploadFile = File(...),
    modalities: Optional[str] = None,  # Comma-separated list
    folder_ids: Optional[str] = None,  # Comma-separated list
    top_k: int = 10,
    threshold: float = 0.0,
    db: AsyncSession = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """
    Search using an uploaded audio or video file.

    - **query_type**: Type of uploaded file ('audio' or 'video')
    - **file**: Uploaded file
    - **modalities**: Comma-separated modality filter
    - **folder_ids**: Comma-separated folder ID filter
    - **top_k**: Number of results (1-100)
    - **threshold**: Minimum similarity score
    """
    import tempfile
    import os

    # Validate query type
    if query_type not in ("audio", "video"):
        raise HTTPException(
            status_code=400, detail="query_type must be 'audio' or 'video'"
        )

    # Parse optional parameters
    modality_list = modalities.split(",") if modalities else None
    folder_id_list = (
        [int(fid) for fid in folder_ids.split(",")] if folder_ids else None
    )

    # Save uploaded file temporarily
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=f".{file.filename or 'tmp'}"
        ) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name

        # Create search request
        request = SearchRequest(
            query=temp_path,
            query_type=query_type,
            modalities=modality_list,
            folder_ids=folder_id_list,
            top_k=top_k,
            threshold=threshold,
        )

        return await search_service.search(db, request)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    finally:
        # Clean up temp file
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/similar/{file_id}", response_model=SearchResponse)
async def find_similar(
    file_id: int,
    top_k: int = 10,
    threshold: float = 0.0,
    db: AsyncSession = Depends(get_db),
    search_service: SearchService = Depends(get_search_service),
) -> SearchResponse:
    """
    Find files similar to a specific indexed file.

    - **file_id**: ID of the reference file
    - **top_k**: Number of results (1-100)
    - **threshold**: Minimum similarity score
    """
    return await search_service.find_similar_files(db, file_id, top_k, threshold)
