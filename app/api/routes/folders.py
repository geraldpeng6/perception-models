"""Folder management API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database.crud import FolderCRUD, FileCRUD
from app.database.schemas import FolderCreate, FolderResponse, FolderUpdate


router = APIRouter(prefix="/api/v1/folders", tags=["folders"])


@router.post("", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    folder: FolderCreate,
    db: AsyncSession = Depends(get_db),
) -> FolderResponse:
    """
    Add a folder to monitor.

    - **path**: Absolute path to folder
    - **modality**: Modality type ('audio', 'video', 'audio_video', 'all')
    """
    # Check if folder already exists
    existing = await FolderCRUD.get_by_path(db, folder.path)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Folder already exists: {folder.path}",
        )

    # Validate path
    from pathlib import Path

    path = Path(folder.path)
    if not path.exists() or not path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid folder path: {folder.path}",
        )

    # Create folder
    created = await FolderCRUD.create(db, folder.path, folder.modality)

    # Start watching
    from app.main import get_watcher

    watcher = get_watcher()
    await watcher.add_folder(folder.path, created.id, db)

    return FolderResponse(
        id=created.id,
        path=created.path,
        modality=created.modality,
        is_active=created.is_active,
        created_at=created.created_at,
        last_indexed_at=created.last_indexed_at,
        file_count=await FileCRUD.count_by_folder(db, created.id),
    )


@router.get("", response_model=List[FolderResponse])
async def list_folders(
    db: AsyncSession = Depends(get_db),
) -> List[FolderResponse]:
    """List all monitored folders."""
    folders = await FolderCRUD.list_all(db)

    return [
        FolderResponse(
            id=f.id,
            path=f.path,
            modality=f.modality,
            is_active=f.is_active,
            created_at=f.created_at,
            last_indexed_at=f.last_indexed_at,
            file_count=await FileCRUD.count_by_folder(db, f.id),
        )
        for f in folders
    ]


@router.get("/{folder_id}", response_model=FolderResponse)
async def get_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
) -> FolderResponse:
    """Get folder by ID."""
    folder = await FolderCRUD.get(db, folder_id)
    if folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
        )

    return FolderResponse(
        id=folder.id,
        path=folder.path,
        modality=folder.modality,
        is_active=folder.is_active,
        created_at=folder.created_at,
        last_indexed_at=folder.last_indexed_at,
        file_count=await FileCRUD.count_by_folder(db, folder.id),
    )


@router.put("/{folder_id}", response_model=FolderResponse)
async def update_folder(
    folder_id: int,
    update: FolderUpdate,
    db: AsyncSession = Depends(get_db),
) -> FolderResponse:
    """
    Update folder configuration.

    - **is_active**: Enable/disable monitoring
    - **modality**: Change modality type
    """
    folder = await FolderCRUD.update(
        db, folder_id, is_active=update.is_active, modality=update.modality
    )

    if folder is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
        )

    return FolderResponse(
        id=folder.id,
        path=folder.path,
        modality=folder.modality,
        is_active=folder.is_active,
        created_at=folder.created_at,
        last_indexed_at=folder.last_indexed_at,
        file_count=await FileCRUD.count_by_folder(db, folder.id),
    )


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: int,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove a folder from monitoring.

    This will also delete all associated files and embeddings.
    """
    # Stop watching
    folder = await FolderCRUD.get(db, folder_id)
    if folder:
        from app.main import get_watcher

        watcher = get_watcher()
        await watcher.remove_folder(folder.path)

    # Delete from database
    success = await FolderCRUD.delete(db, folder_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
        )
