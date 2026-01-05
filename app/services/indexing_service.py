"""Indexing service - orchestrates folder indexing."""

import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.database.crud import FileCRUD, FolderCRUD, IndexingJobCRUD
from app.core.embedding_generator import EmbeddingGenerator
from app.core.file_processor import FileProcessor, ModalityDetector
from app.database.models import Folder


class IndexingService:
    """
    Manages indexing jobs for folders.

    Handles full and incremental scans.
    """

    def __init__(self, embedding_generator: EmbeddingGenerator):
        self.embedding_generator = embedding_generator
        self._active_jobs: dict[int, asyncio.Task] = {}

    async def index_folder(
        self,
        db: AsyncSession,
        folder_id: Optional[int] = None,
        mode: str = "incremental",
    ) -> int:
        """
        Index a folder or all folders.

        Args:
            db: Database session
            folder_id: Folder ID (None for all active folders)
            mode: 'full' or 'incremental'

        Returns:
            Job ID
        """
        # Create indexing job
        job_type = "full_scan" if mode == "full" else "incremental"
        job = await IndexingJobCRUD.create(db, job_type=job_type, folder_id=folder_id)

        # Start job in background
        task = asyncio.create_task(self._perform_indexing(job.id, folder_id, mode))
        self._active_jobs[job.id] = task

        logger.info(f"Started indexing job {job.id} for folder {folder_id}")
        return job.id

    async def _perform_indexing(
        self, job_id: int, folder_id: Optional[int], mode: str
    ) -> None:
        """
        Perform the actual indexing.

        Args:
            job_id: Job ID
            folder_id: Folder ID (None for all folders)
            mode: 'full' or 'incremental'
        """
        from app.database.connection import get_db_context

        async with get_db_context() as db:
            # Update job status
            await IndexingJobCRUD.update_status(db, job_id, "running")

            try:
                # Get folders to index
                if folder_id:
                    folders = [await FolderCRUD.get(db, folder_id)]
                    folders = [f for f in folders if f is not None and f.is_active]
                else:
                    folders = await FolderCRUD.list_all(db, active_only=True)

                if not folders:
                    await IndexingJobCRUD.update_status(
                        db, job_id, "completed"
                    )
                    return

                # Collect all files to process
                all_files = []
                for folder in folders:
                    folder_files = self._scan_folder(folder.path, folder.modality)
                    all_files.extend(folder_files)

                # Set total files
                await IndexingJobCRUD.set_total_files(db, job_id, len(all_files))

                # Process files
                for file_info in all_files:
                    try:
                        await self._index_file(db, file_info)
                        await IndexingJobCRUD.increment_progress(db, job_id)
                    except Exception as e:
                        logger.error(f"Failed to index {file_info['path']}: {e}")
                        await IndexingJobCRUD.increment_progress(
                            db, job_id, failed=1
                        )

                # Update folder timestamps
                for folder in folders:
                    await FolderCRUD.update_last_indexed(db, folder.id, datetime.utcnow())

                # Mark job as completed
                await IndexingJobCRUD.update_status(db, job_id, "completed")

                logger.info(
                    f"Completed indexing job {job_id}: "
                    f"{len(all_files)} files processed"
                )

            except Exception as e:
                logger.error(f"Indexing job {job_id} failed: {e}")
                await IndexingJobCRUD.update_status(
                    db, job_id, "failed", error_message=str(e)
                )

            finally:
                # Clean up task reference
                self._active_jobs.pop(job_id, None)

    def _scan_folder(self, folder_path: str, modality: str) -> list[dict]:
        """
        Scan folder for supported files.

        Args:
            folder_path: Path to folder
            modality: Modality filter ('all', 'audio', 'video', 'audio_video')

        Returns:
            List of file info dicts
        """
        folder = Path(folder_path)
        files = []

        # Define extensions to scan
        extensions = set()
        if modality in ("all", "audio"):
            extensions.update(ModalityDetector.AUDIO_EXTENSIONS)
        if modality in ("all", "video", "audio_video"):
            extensions.update(ModalityDetector.VIDEO_EXTENSIONS)

        # Scan directory
        for ext in extensions:
            for file_path in folder.rglob(f"*{ext}"):
                if file_path.is_file():
                    files.append(
                        {
                            "path": str(file_path.absolute()),
                            "filename": file_path.name,
                            "modality": ModalityDetector.detect(str(file_path)),
                        }
                    )

        return files

    async def _index_file(self, db: AsyncSession, file_info: dict) -> None:
        """
        Index a single file.

        Args:
            db: Database session
            file_info: File info dict
        """
        path = file_info["path"]
        modality = file_info["modality"]

        # Validate file
        is_valid, _ = FileProcessor.validate_file(path)
        if not is_valid:
            return

        # Check if file exists in database, create if not
        file = await FileCRUD.get_by_path(db, path)

        if file is None:
            # Find folder_id from path
            folder_id = None
            folders = await FolderCRUD.list_all(db, active_only=True)
            for folder in folders:
                if path.startswith(folder.path):
                    folder_id = folder.id
                    break

            if folder_id is None:
                # No matching folder found, skip
                return

            # Create file record
            file_info = FileProcessor.get_file_info(path)
            file = await FileCRUD.create(
                db,
                folder_id=folder_id,
                path=path,
                filename=file_info["filename"],
                modality=file_info["modality"],
                file_size=file_info["file_size"],
                mime_type=FileProcessor.get_mime_type(path),
            )

        # Generate embedding
        embedding = await self.embedding_generator.generate_embedding_for_file(
            path, modality
        )

        if embedding is None:
            return

        # Update or create embedding
        from app.database.crud import EmbeddingCRUD

        existing_embeddings = await EmbeddingCRUD.get_by_file(db, file.id)

        if existing_embeddings:
            # Update existing
            for emb in existing_embeddings:
                from app.database.crud import serialize_array

                emb.vector = serialize_array(embedding)
            await FileCRUD.update_indexed_at(db, file.id)
        else:
            # Create new
            await EmbeddingCRUD.create(
                db,
                file_id=file.id,
                vector=embedding,
                modality=modality,
                embedding_type=f"{modality}_embeds",
            )

    async def get_job_status(self, db: AsyncSession, job_id: int) -> Optional[dict]:
        """
        Get status of an indexing job.

        Args:
            db: Database session
            job_id: Job ID

        Returns:
            Job info dict or None
        """
        job = await IndexingJobCRUD.get(db, job_id)
        if job is None:
            return None

        return {
            "id": job.id,
            "job_type": job.job_type,
            "folder_id": job.folder_id,
            "status": job.status,
            "total_files": job.total_files,
            "processed_files": job.processed_files,
            "failed_files": job.failed_files,
            "error_message": job.error_message,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
        }

    async def list_recent_jobs(
        self, db: AsyncSession, limit: int = 50
    ) -> list[dict]:
        """
        List recent indexing jobs.

        Args:
            db: Database session
            limit: Maximum number of jobs

        Returns:
            List of job info dicts
        """
        jobs = await IndexingJobCRUD.list_recent(db, limit=limit)

        return [
            {
                "id": job.id,
                "job_type": job.job_type,
                "folder_id": job.folder_id,
                "status": job.status,
                "total_files": job.total_files,
                "processed_files": job.processed_files,
                "failed_files": job.failed_files,
                "error_message": job.error_message,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
            }
            for job in jobs
        ]
